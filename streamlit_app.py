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

            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                base_yield REAL NOT NULL,
                ingredients TEXT NOT NULL,
                instructions TEXT
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                product_name TEXT NOT NULL,
                quantity REAL NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT NOT NULL,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS finance (
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
                min_level REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                unit_price REAL NOT NULL,
                unit_cost REAL NOT NULL
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


def dashboard_tab() -> None:
    with get_conn() as conn:
        total_recipes = conn.execute("SELECT COUNT(*) c FROM recipes").fetchone()["c"]
        open_orders = conn.execute("SELECT COUNT(*) c FROM orders WHERE status != 'Entregue'").fetchone()["c"]
        stock_alert = conn.execute("SELECT COUNT(*) c FROM inventory WHERE quantity <= min_level").fetchone()["c"]
        finances = conn.execute(
            """
            SELECT
                SUM(CASE WHEN type='entrada' THEN amount ELSE 0 END) entradas,
                SUM(CASE WHEN type='saida' THEN amount ELSE 0 END) saidas
            FROM finance
            """
        ).fetchone()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Receitas", total_recipes)
    c2.metric("Encomendas em aberto", open_orders)
    c3.metric("Alertas de estoque", stock_alert)
    c4.metric("Saldo", f"R$ {(finances['entradas'] or 0) - (finances['saidas'] or 0):.2f}")


def recipes_tab() -> None:
    st.subheader("Receitas e impressão")
    with st.form("recipe_form"):
        name = st.text_input("Nome da receita")
        category = st.text_input("Categoria")
        base_yield = st.number_input("Rendimento base", min_value=0.1, value=1.0, step=0.1)
        ingredients = st.text_area("Ingredientes (1 linha por item)")
        instructions = st.text_area("Modo de preparo")
        if st.form_submit_button("Salvar receita"):
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO recipes (name, category, base_yield, ingredients, instructions) VALUES (?, ?, ?, ?, ?)",
                    (name, category, base_yield, ingredients, instructions),
                )
            st.success("Receita salva.")

    with get_conn() as conn:
        recipes = conn.execute("SELECT * FROM recipes ORDER BY name").fetchall()

    if recipes:
        options = {f"{r['name']} ({r['category']})": r for r in recipes}
        selected_label = st.selectbox("Receita para produção do dia", list(options.keys()))
        selected = options[selected_label]
        desired_qty = st.number_input("Quantidade para produção", min_value=0.1, value=float(selected["base_yield"]), step=0.1)
        factor = desired_qty / float(selected["base_yield"])

        st.markdown(f"<span class='gold-badge'>Fator de escala: x{factor:.2f}</span>", unsafe_allow_html=True)
        st.write("### Ingredientes")
        for line in selected["ingredients"].splitlines():
            st.write(f"- {line}")
        st.write("### Modo de preparo")
        st.write(selected["instructions"] or "-")
        st.info("Use Ctrl/Cmd + P no navegador para imprimir esta receita.")


def orders_tab() -> None:
    st.subheader("Agenda de encomendas")
    with st.form("orders_form"):
        customer = st.text_input("Cliente")
        product = st.text_input("Produto")
        quantity = st.number_input("Quantidade", min_value=0.1, value=1.0, step=0.1)
        due_date = st.date_input("Data de entrega", value=date.today())
        status = st.selectbox("Status", ["Pendente", "Em produção", "Entregue"])
        notes = st.text_area("Observações")
        if st.form_submit_button("Salvar encomenda"):
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO orders (customer_name, product_name, quantity, due_date, status, notes) VALUES (?, ?, ?, ?, ?, ?)",
                    (customer, product, quantity, due_date.isoformat(), status, notes),
                )
            st.success("Encomenda salva.")

    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM orders ORDER BY due_date ASC").fetchall()
    st.dataframe([dict(r) for r in rows], use_container_width=True)


def finance_tab() -> None:
    st.subheader("Financeiro")
    with st.form("finance_form"):
        ftype = st.selectbox("Tipo", ["entrada", "saida"])
        category = st.text_input("Categoria")
        description = st.text_input("Descrição")
        amount = st.number_input("Valor", min_value=0.01, value=1.0, step=0.5)
        fdate = st.date_input("Data", value=date.today())
        if st.form_submit_button("Registrar"):
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO finance (type, category, description, amount, date) VALUES (?, ?, ?, ?, ?)",
                    (ftype, category, description, amount, fdate.isoformat()),
                )
            st.success("Lançamento financeiro salvo.")

    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM finance ORDER BY date DESC").fetchall()
    st.dataframe([dict(r) for r in rows], use_container_width=True)


def inventory_tab() -> None:
    st.subheader("Estoque")
    with st.form("inventory_form"):
        item = st.text_input("Item")
        unit = st.text_input("Unidade")
        qty = st.number_input("Quantidade", min_value=0.0, value=0.0, step=0.5)
        min_level = st.number_input("Estoque mínimo", min_value=0.0, value=0.0, step=0.5)
        if st.form_submit_button("Salvar item"):
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO inventory (item_name, unit, quantity, min_level) VALUES (?, ?, ?, ?)",
                    (item, unit, qty, min_level),
                )
            st.success("Item salvo.")

    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM inventory ORDER BY item_name").fetchall()
    data = [dict(r) for r in rows]
    st.dataframe(data, use_container_width=True)
    alerts = [r for r in data if r["quantity"] <= r["min_level"]]
    if alerts:
        st.warning(f"{len(alerts)} item(ns) abaixo do mínimo.")


def products_tab() -> None:
    st.subheader("Produtos e custo unitário")
    with st.form("products_form"):
        name = st.text_input("Produto")
        unit_price = st.number_input("Preço unitário", min_value=0.01, value=1.0, step=0.5)
        unit_cost = st.number_input("Custo unitário", min_value=0.0, value=0.0, step=0.5)
        if st.form_submit_button("Salvar produto"):
            with get_conn() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO products (name, unit_price, unit_cost) VALUES (?, ?, ?)",
                    (name, unit_price, unit_cost),
                )
            st.success("Produto salvo.")

    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM products ORDER BY name").fetchall()
    out = []
    for r in rows:
        item = dict(r)
        item["margin"] = round(item["unit_price"] - item["unit_cost"], 2)
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
