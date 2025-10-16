from pathlib import Path
import sqlite3

import pandas as pd
import streamlit as st

DB = Path(__file__).resolve().parent / "data" / "market.db"

st.set_page_config(page_title="Offline Market Bot — Nível 0", layout="wide")
st.title("📊 Offline Market Bot — Nível 0 (Coleta)")

if not DB.exists():
    st.warning("Banco ainda não existe. Rode `python -m src.main scan` primeiro.")
    st.stop()

con = sqlite3.connect(DB)
q = """
SELECT timestamp, source_view, item_name, price, qty_visible, page_index, scroll_pos, confidence
FROM prices_snapshots
ORDER BY datetime(timestamp) DESC
"""
df = pd.read_sql(q, con)
tab1, tab2, tab3 = st.tabs(["📈 Snapshots", "🧾 Ações (log)", "📚 Items"])

with tab1:
    left, right = st.columns([2, 1])
    with left:
        item_filter = st.text_input("Filtrar por item (contém):", "")
        view = st.selectbox("Lista", ["TODAS", "BUY_LIST", "SELL_LIST"])
        if item_filter:
            df = df[df["item_name"].str.contains(item_filter, case=False, na=False)]
        if view != "TODAS":
            df = df[df["source_view"] == view]

        st.dataframe(df, use_container_width=True)

    with right:
        st.metric("Linhas coletadas", len(df))
        st.download_button(
            "Exportar CSV",
            df.to_csv(index=False).encode("utf-8"),
            "nivel0_prices.csv",
            "text/csv",
        )

with tab2:
    try:
        qa = """
        SELECT ts, run_id, action, success, notes, details
        FROM actions_log
        ORDER BY datetime(ts) DESC
        """
        df_a = pd.read_sql(qa, con)
        st.dataframe(df_a, use_container_width=True)
        st.download_button(
            "Exportar Log (CSV)",
            df_a.to_csv(index=False).encode("utf-8"),
            "actions_log.csv",
            "text/csv",
        )
    except Exception:
        st.info("Ainda não há `actions_log` (rode um scan/watchlist depois do update do schema).")

with tab3:
    try:
        qi = "SELECT name, category, subcategory, tags, source, created_at, updated_at FROM items ORDER BY name"
        df_i = pd.read_sql(qi, con)
        c1, c2 = st.columns(2)
        with c1:
            cat = st.text_input("Filtrar categoria contém", "")
        with c2:
            tag = st.text_input("Filtrar tag contém", "")
        if cat:
            df_i = df_i[df_i["category"].fillna("").str.contains(cat, case=False)]
        if tag:
            df_i = df_i[df_i["tags"].fillna("").str.contains(tag, case=False)]
        st.dataframe(df_i, use_container_width=True)
        st.download_button(
            "Exportar catálogo CSV",
            df_i.to_csv(index=False).encode("utf-8"),
            "items_catalog.csv",
            "text/csv",
        )
    except Exception:
        st.info("Ainda não há tabela `items` (importe via CSV ou varra uma categoria).")
