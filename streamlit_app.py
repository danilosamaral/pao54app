from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import streamlit as st
from werkzeug.security import check_password_hash, generate_password_hash

DB_PATH = Path("pao54_streamlit.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
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
                min_level REAL NOT NULL
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
                status TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );

            CREATE TABLE IF NOT EXISTS finance (
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

        user = conn.execute("SELECT id FROM users WHERE email = ?", ("admin@pao54.local",)).fetchone()
        if user is None:
            conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                ("Admin Pão 54", "admin@pao54.local", generate_password_hash("pao54admin")),
            )


def set_theme() -> None:
    st.markdown(
        """
        <style>
            :root {
                --black: #111111;
                --gold: #C8A24B;
                --white: #FFFFFF;
                --red: #A6192E;
            }
            .stApp { background-color: #F5F5F5; }
            h1, h2, h3 { color: var(--black); }
            .gold-badge {
                background: var(--gold);
                color: var(--black);
                padding: .25rem .5rem;
                border-radius: .5rem;
                font-weight: 700;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def login_page() -> None:
    st.title("🥖 Pão 54")
    st.caption("Gestão online da micropadaria")
    with st.form("login"):
        email = st.text_input("E-mail")
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar")

    if submitted:
        with get_conn() as conn:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            st.session_state["auth"] = True
            st.session_state["user_name"] = user["name"]
            st.rerun()
        st.error("Credenciais inválidas.")


def latest_unit_cost(conn: sqlite3.Connection, ingredient_name: str) -> float:
    row = conn.execute(
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


def refresh_recipe_cost(conn: sqlite3.Connection, recipe_id: int) -> None:
    ingredients = conn.execute(
        """
        SELECT ri.id, ri.quantity, inv.item_name
        FROM recipe_ingredients ri
        JOIN inventory inv ON inv.id = ri.inventory_item_id
        WHERE ri.recipe_id = ?
        """,
        (recipe_id,),
    ).fetchall()

    total_cost = 0.0
    for ing in ingredients:
        unit_cost = latest_unit_cost(conn, ing["item_name"])
        line_cost = float(ing["quantity"]) * unit_cost
        total_cost += line_cost
        conn.execute(
            "UPDATE recipe_ingredients SET unit_cost_snapshot = ?, total_cost_snapshot = ? WHERE id = ?",
            (unit_cost, line_cost, ing["id"]),
        )

    conn.execute("UPDATE recipes SET total_cost = ? WHERE id = ?", (total_cost, recipe_id))


def dashboard_tab() -> None:
    with get_conn() as conn:
        total_recipes = conn.execute("SELECT COUNT(*) c FROM recipes").fetchone()["c"]
        open_orders = conn.execute("SELECT COUNT(*) c FROM orders WHERE status != 'Entregue'").fetchone()["c"]
        stock_alert = conn.execute("SELECT COUNT(*) c FROM inventory WHERE quantity <= min_level").fetchone()["c"]
        customers = conn.execute("SELECT COUNT(*) c FROM customers").fetchone()["c"]
        finances = conn.execute(
            """
            SELECT
                SUM(CASE WHEN type='entrada' THEN amount ELSE 0 END) entradas,
                SUM(CASE WHEN type='saida' THEN amount ELSE 0 END) saidas
            FROM finance
            """
        ).fetchone()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Receitas", total_recipes)
    c2.metric("Encomendas em aberto", open_orders)
    c3.metric("Alertas estoque", stock_alert)
    c4.metric("Clientes", customers)
    c5.metric("Saldo", f"R$ {(finances['entradas'] or 0) - (finances['saidas'] or 0):.2f}")


def recipes_tab() -> None:
    st.subheader("Receitas")

    with st.form("create_recipe"):
        r_name = st.text_input("Nome da receita")
        r_category = st.text_input("Categoria")
        r_yield = st.number_input("Rendimento base", min_value=0.1, value=1.0, step=0.1)
        if st.form_submit_button("Criar receita"):
            if r_name and r_category:
                with get_conn() as conn:
                    conn.execute(
                        "INSERT OR IGNORE INTO recipes (name, category, base_yield) VALUES (?, ?, ?)",
                        (r_name, r_category, r_yield),
                    )
                st.success("Receita criada.")

    with get_conn() as conn:
        recipes = conn.execute("SELECT * FROM recipes ORDER BY name").fetchall()
        inventory_items = conn.execute("SELECT * FROM inventory ORDER BY item_name").fetchall()

    if not recipes:
        st.info("Cadastre uma receita para continuar.")
        return

    selected_recipe_label = st.selectbox("Selecione a receita", [f"{r['name']} ({r['category']})" for r in recipes])
    selected_recipe = next(r for r in recipes if f"{r['name']} ({r['category']})" == selected_recipe_label)

    if not inventory_items:
        st.warning("Cadastre ingredientes no estoque antes de adicionar na receita.")
        return

    with st.form("add_ingredient"):
        ingredient_map = {f"{i['item_name']} ({i['unit']})": i for i in inventory_items}
        ingredient_label = st.selectbox("Ingrediente (apenas itens do estoque)", list(ingredient_map.keys()))
        ing_qty = st.number_input("Quantidade", min_value=0.01, value=1.0, step=0.1)
        ing_unit = st.selectbox("Unidade", ["g", "kg", "ml", "L", "un"])
        if st.form_submit_button("Adicionar ingrediente"):
            ingredient = ingredient_map[ingredient_label]
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO recipe_ingredients (recipe_id, inventory_item_id, quantity, unit) VALUES (?, ?, ?, ?)",
                    (selected_recipe["id"], ingredient["id"], ing_qty, ing_unit),
                )
                refresh_recipe_cost(conn, selected_recipe["id"])
            st.success("Ingrediente adicionado e custo da receita atualizado.")

    with get_conn() as conn:
        refresh_recipe_cost(conn, selected_recipe["id"])
        recipe_rows = conn.execute(
            """
            SELECT ri.id, inv.item_name, ri.quantity, ri.unit, ri.unit_cost_snapshot, ri.total_cost_snapshot
            FROM recipe_ingredients ri
            JOIN inventory inv ON inv.id = ri.inventory_item_id
            WHERE ri.recipe_id = ?
            ORDER BY ri.id DESC
            """,
            (selected_recipe["id"],),
        ).fetchall()
        recipe_total = conn.execute("SELECT total_cost FROM recipes WHERE id = ?", (selected_recipe["id"],)).fetchone()["total_cost"]

    st.write("### Ingredientes da receita")
    st.dataframe([dict(r) for r in recipe_rows], use_container_width=True)
    st.markdown(f"<span class='gold-badge'>Custo total da receita: R$ {recipe_total:.2f}</span>", unsafe_allow_html=True)

    prod_qty = st.number_input("Quantidade para produção do dia", min_value=0.1, value=float(selected_recipe["base_yield"]), step=0.1)
    factor = prod_qty / float(selected_recipe["base_yield"])
    st.write(f"Fator de escala: x{factor:.2f}")

    for row in recipe_rows:
        st.write(f"- {row['item_name']}: {row['quantity'] * factor:.2f} {row['unit']}")


def customers_editor(conn: sqlite3.Connection) -> None:
    customers = conn.execute("SELECT * FROM customers ORDER BY name").fetchall()
    st.write("### Clientes cadastrados")
    st.dataframe([dict(c) for c in customers], use_container_width=True)

    if customers:
        options = {f"{c['id']} - {c['name']}": c for c in customers}
        selected = options[st.selectbox("Editar/Excluir cliente", list(options.keys()))]

        with st.form("edit_customer"):
            name = st.text_input("Nome", value=selected["name"])
            phone = st.text_input("Telefone", value=selected["phone"] or "")
            email = st.text_input("Email", value=selected["email"] or "")
            notes = st.text_area("Observações", value=selected["notes"] or "")
            col1, col2 = st.columns(2)
            update = col1.form_submit_button("Atualizar cliente")
            delete = col2.form_submit_button("Excluir cliente")

            if update:
                conn.execute(
                    "UPDATE customers SET name=?, phone=?, email=?, notes=? WHERE id=?",
                    (name, phone, email, notes, selected["id"]),
                )
                st.success("Cliente atualizado.")
            if delete:
                conn.execute("DELETE FROM customers WHERE id=?", (selected["id"],))
                st.warning("Cliente excluído.")


def orders_tab() -> None:
    st.subheader("Encomendas")
    with get_conn() as conn:
        customers = conn.execute("SELECT * FROM customers ORDER BY name").fetchall()

        with st.expander("Cadastrar cliente", expanded=False):
            with st.form("customer_form"):
                name = st.text_input("Nome do cliente")
                phone = st.text_input("Telefone")
                email = st.text_input("Email")
                notes = st.text_area("Observações")
                if st.form_submit_button("Salvar cliente"):
                    conn.execute(
                        "INSERT INTO customers (name, phone, email, notes) VALUES (?, ?, ?, ?)",
                        (name, phone, email, notes),
                    )
                    st.success("Cliente salvo.")

        customers_editor(conn)
        customers = conn.execute("SELECT * FROM customers ORDER BY name").fetchall()

        if not customers:
            st.info("Cadastre pelo menos um cliente para criar encomendas.")
            return

        with st.form("orders_form"):
            customer_map = {f"{c['id']} - {c['name']}": c for c in customers}
            customer_label = st.selectbox("Cliente", list(customer_map.keys()))
            product = st.text_input("Produto")
            quantity = st.number_input("Quantidade", min_value=0.1, value=1.0, step=0.1)
            unit_price = st.number_input("Preço unitário", min_value=0.0, value=0.0, step=0.5)
            due_date = st.date_input("Data de entrega", value=date.today())
            status = st.selectbox("Status", ["Pendente", "Em produção", "Entregue"])
            notes = st.text_area("Observações do pedido")
            if st.form_submit_button("Salvar encomenda"):
                customer = customer_map[customer_label]
                total_price = quantity * unit_price
                conn.execute(
                    """
                    INSERT INTO orders (customer_id, product_name, quantity, unit_price, total_price, due_date, status, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (customer["id"], product, quantity, unit_price, total_price, due_date.isoformat(), status, notes),
                )
                st.success("Encomenda salva.")

        orders = conn.execute(
            """
            SELECT o.*, c.name AS customer_name
            FROM orders o
            JOIN customers c ON c.id = o.customer_id
            ORDER BY o.due_date DESC
            """
        ).fetchall()

        st.write("### Histórico de vendas por cliente")
        st.dataframe([dict(o) for o in orders], use_container_width=True)

        if orders:
            order_map = {f"{o['id']} - {o['customer_name']} - {o['product_name']}": o for o in orders}
            selected = order_map[st.selectbox("Editar/Excluir encomenda", list(order_map.keys()))]
            with st.form("edit_order"):
                product = st.text_input("Produto", value=selected["product_name"])
                quantity = st.number_input("Quantidade", min_value=0.1, value=float(selected["quantity"]), step=0.1)
                unit_price = st.number_input("Preço unitário", min_value=0.0, value=float(selected["unit_price"]), step=0.5)
                due_date = st.date_input("Data entrega", value=date.fromisoformat(selected["due_date"]))
                status = st.selectbox("Status", ["Pendente", "Em produção", "Entregue"], index=["Pendente", "Em produção", "Entregue"].index(selected["status"]))
                notes = st.text_area("Observações", value=selected["notes"] or "")
                col1, col2 = st.columns(2)
                update = col1.form_submit_button("Atualizar encomenda")
                delete = col2.form_submit_button("Excluir encomenda")

                if update:
                    total_price = quantity * unit_price
                    conn.execute(
                        """
                        UPDATE orders
                        SET product_name=?, quantity=?, unit_price=?, total_price=?, due_date=?, status=?, notes=?
                        WHERE id=?
                        """,
                        (product, quantity, unit_price, total_price, due_date.isoformat(), status, notes, selected["id"]),
                    )
                    st.success("Encomenda atualizada.")
                if delete:
                    conn.execute("DELETE FROM orders WHERE id=?", (selected["id"],))
                    st.warning("Encomenda excluída.")


def finance_tab() -> None:
    st.subheader("Financeiro")
    with get_conn() as conn:
        with st.form("finance_form"):
            ftype = st.selectbox("Tipo", ["entrada", "saida"])
            category = st.text_input("Categoria")
            description = st.text_input("Descrição")
            amount = st.number_input("Valor", min_value=0.01, value=1.0, step=0.5)
            fdate = st.date_input("Data", value=date.today())
            if st.form_submit_button("Registrar"):
                conn.execute(
                    "INSERT INTO finance (type, category, description, amount, date) VALUES (?, ?, ?, ?, ?)",
                    (ftype, category, description, amount, fdate.isoformat()),
                )
                st.success("Lançamento financeiro salvo.")

        rows = conn.execute("SELECT * FROM finance ORDER BY date DESC").fetchall()
        st.dataframe([dict(r) for r in rows], use_container_width=True)


def inventory_tab() -> None:
    st.subheader("Estoque de ingredientes")
    with get_conn() as conn:
        with st.form("inventory_form"):
            item = st.text_input("Ingrediente")
            unit = st.selectbox("Unidade padrão", ["g", "kg", "ml", "L", "un"])
            qty = st.number_input("Quantidade", min_value=0.0, value=0.0, step=0.5)
            min_level = st.number_input("Estoque mínimo", min_value=0.0, value=0.0, step=0.5)
            if st.form_submit_button("Salvar item"):
                conn.execute(
                    "INSERT OR REPLACE INTO inventory (item_name, unit, quantity, min_level) VALUES (?, ?, ?, ?)",
                    (item, unit, qty, min_level),
                )
                st.success("Item salvo.")

        rows = conn.execute("SELECT * FROM inventory ORDER BY item_name").fetchall()
        data = [dict(r) for r in rows]
        st.dataframe(data, use_container_width=True)


def products_tab() -> None:
    st.subheader("Produtos e custo unitário (histórico de preços)")
    with get_conn() as conn:
        with st.form("price_history_form"):
            product_name = st.text_input("Produto")
            brand = st.text_input("Marca")
            package_amount = st.number_input("Peso/volume da embalagem", min_value=0.01, value=1.0, step=0.1)
            package_unit = st.selectbox("Unidade da embalagem", ["g", "kg", "ml", "L", "un"])
            price = st.number_input("Preço", min_value=0.01, value=1.0, step=0.5)
            price_date = st.date_input("Data do preço", value=date.today())
            location = st.text_input("Local de compra")
            if st.form_submit_button("Registrar preço"):
                conn.execute(
                    """
                    INSERT INTO product_price_history (product_name, brand, package_amount, package_unit, price, price_date, location)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (product_name, brand, package_amount, package_unit, price, price_date.isoformat(), location),
                )
                st.success("Preço registrado.")

        history = conn.execute(
            "SELECT * FROM product_price_history ORDER BY product_name, price_date DESC, id DESC"
        ).fetchall()
        out = []
        for row in history:
            item = dict(row)
            item["unit_cost"] = round(item["price"] / item["package_amount"], 4)
            out.append(item)
        st.dataframe(out, use_container_width=True)


def app() -> None:
    st.set_page_config(page_title="Pão 54", page_icon="🥖", layout="wide")
    set_theme()
    init_db()

    if not st.session_state.get("auth"):
        login_page()
        return

    st.title("🥖 Plataforma Pão 54")
    st.caption(f"Bem-vindo, {st.session_state.get('user_name', 'usuário')}.")

    if st.button("Sair"):
        st.session_state.clear()
        st.rerun()

    tabs = st.tabs(["Dashboard", "Receitas", "Encomendas", "Financeiro", "Estoque", "Produtos"])
    with tabs[0]:
        dashboard_tab()
    with tabs[1]:
        recipes_tab()
    with tabs[2]:
        orders_tab()
    with tabs[3]:
        finance_tab()
    with tabs[4]:
        inventory_tab()
    with tabs[5]:
        products_tab()


if __name__ == "__main__":
    app()
