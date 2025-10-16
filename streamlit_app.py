import sqlite3
from pathlib import Path

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
