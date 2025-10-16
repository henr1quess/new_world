from pathlib import Path
import sqlite3
import subprocess
import sys

import pandas as pd
import streamlit as st

# --- Config de página deve vir primeiro ---
st.set_page_config(page_title="Offline Market Bot — Nível 0", layout="wide")
st.title("📊 Offline Market Bot — Nível 0 (Coleta)")

BASE_DIR = Path(__file__).resolve().parent
DB = BASE_DIR / "data" / "market.db"
CWD = str(BASE_DIR)  # trabalhar sempre a partir da raiz do projeto do app

# --- Helpers ---
def _run_bg(args: list[str]) -> None:
    """Dispara um comando em background e mostra toast."""
    try:
        subprocess.Popen(args, cwd=CWD)
        st.toast("Tarefa iniciada em segundo plano.", icon="✅")
    except Exception as e:
        st.error(f"Falha ao iniciar processo: {e}")

@st.cache_data(ttl=5)
def _read_sql(query: str) -> pd.DataFrame:
    con = sqlite3.connect(DB)
    try:
        return pd.read_sql(query, con)
    finally:
        con.close()

def _refresh_now():
    st.cache_data.clear()
    st.rerun()

# --- Sidebar: Controles ---
with st.sidebar:
    st.header("⚙️ Controles")

    # Scan simples
    source = st.selectbox("Lista p/ Scan", ["BUY_LIST", "SELL_LIST"])
    pages = st.number_input("Páginas", 1, 50, 3)
    if st.button("Iniciar Scan (sem digitar)"):
        _run_bg(
            [
                sys.executable,
                "-m",
                "src.main",
                "scan",
                "--source-view",
                source,
                "--pages",
                str(pages),
            ]
        )

    st.divider()

    # Watchlist
    wl = st.text_input("Watchlist CSV", "data/watchlist.csv")
    views = st.multiselect(
        "Views", ["BUY_LIST", "SELL_LIST"], default=["BUY_LIST", "SELL_LIST"]
    )
    if st.button("Scan Watchlist"):
        _run_bg(
            [
                sys.executable,
                "-m",
                "src.main",
                "scan-watchlist",  # Typer converte _ para -
                "--source-view",
                "BUY_LIST",
                "--watchlist-csv",
                wl,
                "--views",
                ",".join(views),
            ]
        )

    st.divider()

    # Jobs
    jobs_file = st.text_input("Jobs YAML", "config/jobs.yaml")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Run Jobs (1x)"):
            _run_bg(
                [
                    sys.executable,
                    "-m",
                    "src.main",
                    "run-jobs",  # Typer: run_jobs -> run-jobs
                    "--file",
                    jobs_file,
                ]
            )
    with c2:
        if st.button("Watch Jobs (auto)"):
            _run_bg(
                [
                    sys.executable,
                    "-m",
                    "src.main",
                    "watch-jobs",  # Typer: watch_jobs -> watch-jobs
                    "--file",
                    jobs_file,
                ]
            )

    st.divider()
    if st.button("🔄 Atualizar agora"):
        _refresh_now()

# --- Banco ---
if not DB.exists():
    st.warning("Banco ainda não existe. Rode um scan pela sidebar ou via CLI uma vez.")
    st.stop()

# --- UI principal ---
tab1, tab2, tab3 = st.tabs(["📈 Snapshots", "🧾 Ações (log)", "📚 Items"])

with tab1:
    df = _read_sql(
        """
        SELECT timestamp, source_view, item_name, price, qty_visible, page_index, scroll_pos, confidence
        FROM prices_snapshots
        ORDER BY datetime(timestamp) DESC
        """
    )
    top = st.container()
    left, right = st.columns([2, 1])

    with left:
        cols1 = st.columns(2)
        with cols1[0]:
            item_filter = st.text_input("Filtrar por item (contém):", "")
        with cols1[1]:
            view = st.selectbox("Lista", ["TODAS", "BUY_LIST", "SELL_LIST"])

        if item_filter:
            df = df[df["item_name"].str.contains(item_filter, case=False, na=False)]
        if view != "TODAS":
            df = df[df["source_view"] == view]

        st.dataframe(df, use_container_width=True)

    with right:
        st.metric("Linhas coletadas (filtro aplicado)", len(df))
        if not df.empty:
            st.metric("Última captura", str(df["timestamp"].max()))
        st.download_button(
            "Exportar CSV",
            df.to_csv(index=False).encode("utf-8"),
            "nivel0_prices.csv",
            "text/csv",
        )

with tab2:
    try:
        df_a = _read_sql(
            """
            SELECT ts, run_id, action, success, notes, details
            FROM actions_log
            ORDER BY datetime(ts) DESC
            """
        )
        st.dataframe(df_a, use_container_width=True)
        st.download_button(
            "Exportar Log (CSV)",
            df_a.to_csv(index=False).encode("utf-8"),
            "actions_log.csv",
            "text/csv",
        )
    except Exception:
        st.info(
            "Ainda não há `actions_log` (rode um scan/watchlist depois do update do schema)."
        )

with tab3:
    try:
        df_i = _read_sql(
            """
            SELECT name, category, subcategory, tags, source, created_at, updated_at
            FROM items
            ORDER BY name
            """
        )
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
