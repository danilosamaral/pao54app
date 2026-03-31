from __future__ import annotations

import os
import sqlite3
from functools import wraps
from pathlib import Path
from typing import Any

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "pao54.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("PAO54_SECRET", "pao54-dev-secret")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_: Any) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT UNIQUE NOT NULL,
            unit TEXT NOT NULL,
            quantity REAL NOT NULL,
            min_level REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            base_yield REAL NOT NULL,
            total_cost REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS recipe_ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL,
            inventory_item_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            unit_cost_snapshot REAL NOT NULL DEFAULT 0,
            total_cost_snapshot REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
            FOREIGN KEY (inventory_item_id) REFERENCES inventory(id)
        );

        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit_price REAL NOT NULL DEFAULT 0,
            total_price REAL NOT NULL DEFAULT 0,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pendente',
            notes TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );

        CREATE TABLE IF NOT EXISTS finances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS product_price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            brand TEXT NOT NULL,
            package_amount REAL NOT NULL,
            package_unit TEXT NOT NULL,
            price REAL NOT NULL,
            price_date TEXT NOT NULL,
            location TEXT NOT NULL
        );
        """
    )

    exists = db.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
    if exists == 0:
        db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Admin Pão 54", "admin@pao54.local", generate_password_hash("pao54admin")),
        )
    db.commit()
    db.close()


def latest_unit_cost(db: sqlite3.Connection, ingredient_name: str) -> float:
    row = db.execute(
        """
        SELECT price, package_amount
        FROM product_price_history
        WHERE product_name = ?
        ORDER BY price_date DESC, id DESC
        LIMIT 1
        """,
        (ingredient_name,),
    ).fetchone()
    if not row or row["package_amount"] <= 0:
        return 0.0
    return float(row["price"]) / float(row["package_amount"])


def refresh_recipe_cost(db: sqlite3.Connection, recipe_id: int) -> None:
    rows = db.execute(
        """
        SELECT ri.id, ri.quantity, inv.item_name
        FROM recipe_ingredients ri
        JOIN inventory inv ON inv.id = ri.inventory_item_id
        WHERE ri.recipe_id = ?
        """,
        (recipe_id,),
    ).fetchall()

    total = 0.0
    for row in rows:
        unit_cost = latest_unit_cost(db, row["item_name"])
        line_cost = float(row["quantity"]) * unit_cost
        total += line_cost
        db.execute(
            "UPDATE recipe_ingredients SET unit_cost_snapshot=?, total_cost_snapshot=? WHERE id=?",
            (unit_cost, line_cost, row["id"]),
        )

    db.execute("UPDATE recipes SET total_cost=? WHERE id=?", (total, recipe_id))


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view


@app.route("/")
def root():
    return redirect(url_for("dashboard")) if session.get("user_id") else redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("dashboard"))

        flash("Credenciais inválidas.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    totals = {
        "recipes": db.execute("SELECT COUNT(*) FROM recipes").fetchone()[0],
        "orders": db.execute("SELECT COUNT(*) FROM orders WHERE status != 'Entregue'").fetchone()[0],
        "stock_alerts": db.execute("SELECT COUNT(*) FROM inventory WHERE quantity <= min_level").fetchone()[0],
        "products": db.execute("SELECT COUNT(*) FROM product_price_history").fetchone()[0],
        "customers": db.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
    }

    finance = db.execute(
        """
        SELECT
            SUM(CASE WHEN type='entrada' THEN amount ELSE 0 END) AS entradas,
            SUM(CASE WHEN type='saida' THEN amount ELSE 0 END) AS saidas
        FROM finances
        """
    ).fetchone()

    return render_template("dashboard.html", totals=totals, entradas=finance["entradas"] or 0, saidas=finance["saidas"] or 0)


@app.route("/recipes", methods=["GET", "POST"])
@login_required
def recipes():
    db = get_db()

    if request.method == "POST":
        action = request.form.get("action")
        if action == "create_recipe":
            db.execute(
                "INSERT OR IGNORE INTO recipes (name, category, base_yield) VALUES (?, ?, ?)",
                (request.form["name"], request.form["category"], float(request.form["base_yield"])),
            )
            flash("Receita criada.", "success")

        if action == "add_ingredient":
            recipe_id = int(request.form["recipe_id"])
            db.execute(
                "INSERT INTO recipe_ingredients (recipe_id, inventory_item_id, quantity, unit) VALUES (?, ?, ?, ?)",
                (recipe_id, int(request.form["inventory_item_id"]), float(request.form["quantity"]), request.form["unit"]),
            )
            refresh_recipe_cost(db, recipe_id)
            flash("Ingrediente adicionado e custo atualizado.", "success")

        if action == "delete_ingredient":
            ingredient_id = int(request.form["ingredient_id"])
            recipe_id = int(request.form["recipe_id"])
            db.execute("DELETE FROM recipe_ingredients WHERE id = ?", (ingredient_id,))
            refresh_recipe_cost(db, recipe_id)
            flash("Ingrediente removido.", "success")

        db.commit()
        return redirect(url_for("recipes", recipe_id=request.form.get("recipe_id")))

    all_recipes = db.execute("SELECT * FROM recipes ORDER BY name").fetchall()
    inventory_rows = db.execute("SELECT * FROM inventory ORDER BY item_name").fetchall()

    selected = None
    ingredients = []
    production_qty = None
    factor = 1.0

    recipe_id = request.args.get("recipe_id", type=int)
    if recipe_id:
        selected = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
        if selected:
            refresh_recipe_cost(db, selected["id"])
            db.commit()
            ingredients = db.execute(
                """
                SELECT ri.*, inv.item_name
                FROM recipe_ingredients ri
                JOIN inventory inv ON inv.id = ri.inventory_item_id
                WHERE ri.recipe_id = ?
                ORDER BY ri.id DESC
                """,
                (selected["id"],),
            ).fetchall()
            production_qty = float(request.args.get("production_qty", selected["base_yield"]))
            factor = production_qty / selected["base_yield"] if selected["base_yield"] else 1

    return render_template(
        "recipes.html",
        recipes=all_recipes,
        inventory_items=inventory_rows,
        selected=selected,
        ingredients=ingredients,
        production_qty=production_qty,
        factor=factor,
    )


@app.route("/orders", methods=["GET", "POST"])
@login_required
def orders():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action")

        if action == "create_customer":
            db.execute(
                "INSERT INTO customers (name, phone, email, notes) VALUES (?, ?, ?, ?)",
                (
                    request.form["name"],
                    request.form.get("phone", ""),
                    request.form.get("email", ""),
                    request.form.get("notes", ""),
                ),
            )
            flash("Cliente cadastrado.", "success")

        if action == "update_customer":
            db.execute(
                "UPDATE customers SET name=?, phone=?, email=?, notes=? WHERE id=?",
                (
                    request.form["name"],
                    request.form.get("phone", ""),
                    request.form.get("email", ""),
                    request.form.get("notes", ""),
                    int(request.form["customer_id"]),
                ),
            )
            flash("Cliente atualizado.", "success")

        if action == "delete_customer":
            db.execute("DELETE FROM customers WHERE id=?", (int(request.form["customer_id"]),))
            flash("Cliente removido.", "success")

        if action == "create_order":
            qty = float(request.form["quantity"])
            unit_price = float(request.form["unit_price"])
            db.execute(
                """
                INSERT INTO orders (customer_id, product_name, quantity, unit_price, total_price, due_date, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(request.form["customer_id"]),
                    request.form["product_name"],
                    qty,
                    unit_price,
                    qty * unit_price,
                    request.form["due_date"],
                    request.form["status"],
                    request.form.get("notes", ""),
                ),
            )
            flash("Encomenda cadastrada.", "success")

        if action == "update_order":
            qty = float(request.form["quantity"])
            unit_price = float(request.form["unit_price"])
            db.execute(
                """
                UPDATE orders
                SET customer_id=?, product_name=?, quantity=?, unit_price=?, total_price=?, due_date=?, status=?, notes=?
                WHERE id=?
                """,
                (
                    int(request.form["customer_id"]),
                    request.form["product_name"],
                    qty,
                    unit_price,
                    qty * unit_price,
                    request.form["due_date"],
                    request.form["status"],
                    request.form.get("notes", ""),
                    int(request.form["order_id"]),
                ),
            )
            flash("Encomenda atualizada.", "success")

        if action == "delete_order":
            db.execute("DELETE FROM orders WHERE id=?", (int(request.form["order_id"]),))
            flash("Encomenda removida.", "success")

        db.commit()
        return redirect(url_for("orders"))

    customer_rows = db.execute("SELECT * FROM customers ORDER BY name").fetchall()
    order_rows = db.execute(
        """
        SELECT o.*, c.name AS customer_name
        FROM orders o
        JOIN customers c ON c.id = o.customer_id
        ORDER BY o.due_date DESC
        """
    ).fetchall()

    return render_template("orders.html", customers=customer_rows, orders=order_rows)


@app.route("/finance", methods=["GET", "POST"])
@login_required
def finance():
    db = get_db()
    if request.method == "POST":
        db.execute(
            "INSERT INTO finances (type, category, description, amount, date) VALUES (?, ?, ?, ?, ?)",
            (
                request.form["type"],
                request.form["category"],
                request.form.get("description", ""),
                float(request.form["amount"]),
                request.form["date"],
            ),
        )
        db.commit()
        flash("Lançamento financeiro registrado.", "success")
        return redirect(url_for("finance"))

    entries = db.execute("SELECT * FROM finances ORDER BY date DESC").fetchall()
    return render_template("finance.html", entries=entries)


@app.route("/inventory", methods=["GET", "POST"])
@login_required
def inventory():
    db = get_db()
    if request.method == "POST":
        db.execute(
            "INSERT OR REPLACE INTO inventory (item_name, unit, quantity, min_level) VALUES (?, ?, ?, ?)",
            (
                request.form["item_name"],
                request.form["unit"],
                float(request.form["quantity"]),
                float(request.form["min_level"]),
            ),
        )
        db.commit()
        flash("Item de estoque cadastrado.", "success")
        return redirect(url_for("inventory"))

    items = db.execute("SELECT * FROM inventory ORDER BY item_name").fetchall()
    return render_template("inventory.html", items=items)


@app.route("/products", methods=["GET", "POST"])
@login_required
def products():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create_price":
            db.execute(
                """
                INSERT INTO product_price_history (product_name, brand, package_amount, package_unit, price, price_date, location)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.form["product_name"],
                    request.form["brand"],
                    float(request.form["package_amount"]),
                    request.form["package_unit"],
                    float(request.form["price"]),
                    request.form["price_date"],
                    request.form["location"],
                ),
            )
            flash("Preço registrado.", "success")

        if action == "delete_price":
            db.execute("DELETE FROM product_price_history WHERE id=?", (int(request.form["price_id"]),))
            flash("Registro removido.", "success")

        db.commit()
        return redirect(url_for("products"))

    prices = db.execute(
        "SELECT * FROM product_price_history ORDER BY product_name, price_date DESC, id DESC"
    ).fetchall()
    return render_template("products.html", prices=prices)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
