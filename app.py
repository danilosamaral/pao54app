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
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            base_yield REAL NOT NULL,
            instructions TEXT,
            ingredients TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            product_name TEXT NOT NULL,
            quantity REAL NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pendente',
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS finances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            unit TEXT NOT NULL,
            quantity REAL NOT NULL,
            min_level REAL NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            unit_price REAL NOT NULL,
            unit_cost REAL NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1
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
        "products": db.execute("SELECT COUNT(*) FROM products WHERE active = 1").fetchone()[0],
    }

    finance = db.execute(
        """
        SELECT
            SUM(CASE WHEN type='entrada' THEN amount ELSE 0 END) AS entradas,
            SUM(CASE WHEN type='saida' THEN amount ELSE 0 END) AS saidas
        FROM finances
        """
    ).fetchone()

    recent_orders = db.execute(
        "SELECT * FROM orders ORDER BY due_date ASC LIMIT 5"
    ).fetchall()

    return render_template(
        "dashboard.html",
        totals=totals,
        entradas=finance["entradas"] or 0,
        saidas=finance["saidas"] or 0,
        recent_orders=recent_orders,
    )


@app.route("/recipes", methods=["GET", "POST"])
@login_required
def recipes():
    db = get_db()
    if request.method == "POST":
        db.execute(
            "INSERT INTO recipes (name, category, base_yield, instructions, ingredients) VALUES (?, ?, ?, ?, ?)",
            (
                request.form["name"],
                request.form["category"],
                float(request.form["base_yield"]),
                request.form.get("instructions", ""),
                request.form["ingredients"],
            ),
        )
        db.commit()
        flash("Receita cadastrada com sucesso.", "success")
        return redirect(url_for("recipes"))

    all_recipes = db.execute("SELECT * FROM recipes ORDER BY name").fetchall()
    selected = None
    scaled_ingredients = []
    production_qty = None

    recipe_id = request.args.get("recipe_id")
    if recipe_id:
        selected = db.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,)).fetchone()
        if selected:
            production_qty = float(request.args.get("production_qty", selected["base_yield"]))
            factor = production_qty / selected["base_yield"] if selected["base_yield"] else 1
            for line in selected["ingredients"].splitlines():
                scaled_ingredients.append({"line": line, "factor": round(factor, 2)})

    return render_template(
        "recipes.html",
        recipes=all_recipes,
        selected=selected,
        scaled_ingredients=scaled_ingredients,
        production_qty=production_qty,
    )


@app.route("/orders", methods=["GET", "POST"])
@login_required
def orders():
    db = get_db()
    if request.method == "POST":
        db.execute(
            "INSERT INTO orders (customer_name, product_name, quantity, due_date, status, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (
                request.form["customer_name"],
                request.form["product_name"],
                float(request.form["quantity"]),
                request.form["due_date"],
                request.form["status"],
                request.form.get("notes", ""),
            ),
        )
        db.commit()
        flash("Encomenda salva.", "success")
        return redirect(url_for("orders"))

    all_orders = db.execute("SELECT * FROM orders ORDER BY due_date").fetchall()
    return render_template("orders.html", orders=all_orders)


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
            "INSERT INTO inventory (item_name, unit, quantity, min_level) VALUES (?, ?, ?, ?)",
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
        db.execute(
            "INSERT OR REPLACE INTO products (name, unit_price, unit_cost, active) VALUES (?, ?, ?, 1)",
            (
                request.form["name"],
                float(request.form["unit_price"]),
                float(request.form.get("unit_cost", 0) or 0),
            ),
        )
        db.commit()
        flash("Produto cadastrado/atualizado.", "success")
        return redirect(url_for("products"))

    product_rows = db.execute("SELECT * FROM products ORDER BY name").fetchall()
    return render_template("products.html", products=product_rows)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
