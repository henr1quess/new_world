# Project Snapshot

- **Root**: `C:\Projetos\new_world`
- **Generated**: 2025-10-16 01:36:36
- **Files included**: 20

## Tree (included files only)

```
├── README.md
├── config
│   ├── capture.yaml
│   ├── ocr.yaml
│   └── ui_profiles.yaml
├── project_dump.md
├── reader.py
├── requirements.txt
├── schema.sql
├── src
│   ├── __init__.py
│   ├── capture
│   │   ├── __init__.py
│   │   ├── calibrate.py
│   │   └── window.py
│   ├── main.py
│   ├── ocr
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   └── extract.py
│   ├── storage
│   │   ├── __init__.py
│   │   └── db.py
│   └── utils
│       └── logging.py
└── streamlit_app.py
```

## Files

### config/capture.yaml

> size: 154 bytes

```yaml
window_title_contains: "Market"     # ajuste para o título do seu jogo/janela
max_pages: 50
retry:
  ocr_max_retries: 2
  ocr_retry_delay_ms: 120


```

### config/ocr.yaml

> size: 296 bytes

```yaml
engine_order: ["paddle", "tesseract"]
tesseract:
  path: "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
  psm: 6
  oem: 3
  whitelist: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,-% "
postprocess:
  price_regex: "(\\d+(?:[\\.,]\\d{1,2})?)"
  min_confidence: 0.65

```

### config/ui_profiles.yaml

> size: 449 bytes

```yaml
profiles:
  "2560x1440@100%":
    anchors:
      market_title: {x: 0.50, y: 0.08, w: 0.20, h: 0.05}
      header_row:   {x: 0.10, y: 0.16, w: 0.80, h: 0.05}
      list_zone:    {x: 0.10, y: 0.22, w: 0.80, h: 0.66}
      footer_zone:  {x: 0.10, y: 0.90, w: 0.80, h: 0.06}
    columns:
      name:  {x: 0.02, w: 0.50}
      price: {x: 0.58, w: 0.20}
      qty:   {x: 0.80, w: 0.18}
    scroll:
      step_pixels: 240
      pause_ms: 150

```

### project_dump.md

> size: 0 bytes

```markdown

```

### reader.py

> size: 7623 bytes

```python
#!/usr/bin/env python3
"""
Gera um único arquivo Markdown com:
1) árvore do projeto (apenas itens incluídos)
2) conteúdo integral de cada arquivo selecionado

Exemplos:
    python reader.py --root . --out project_dump.md
    python reader.py --root . --out dump.md --include .py,.yaml,.yml,.sql,.md \
        --include-names schema.sql,README.md,requirements.txt
"""

from __future__ import annotations
import argparse
import datetime as dt
import sys
from pathlib import Path

# ---------- Defaults ----------
# Agora inclui .sql e .md por padrão
DEFAULT_INCLUDE = {".py", ".yaml", ".yml", ".sql", ".md"}
DEFAULT_EXCLUDE_DIRS = {
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache",
    "venv", ".venv", "env", ".env", ".idea", ".vscode",
    "node_modules", "dist", "build"
}
DEFAULT_EXCLUDE_FILES = {".env", ".env.local", ".env.example"}

# Sempre incluir por nome (independente de extensão)
DEFAULT_ALWAYS_INCLUDE_NAMES = {"schema.sql", "README.md", "requirements.txt"}

# ---------- Utils ----------
def is_textual(p: Path) -> bool:
    try:
        raw = p.read_bytes()[:4096]
    except Exception:
        return False
    return b"\x00" not in raw

def ext_to_lang(ext: str, name: str) -> str:
    ext = ext.lower()
    if ext == ".py": return "python"
    if ext in {".yaml", ".yml"}: return "yaml"
    if ext == ".json": return "json"
    if ext == ".toml": return "toml"
    if ext == ".ini": return "ini"
    if ext == ".sql": return "sql"
    if ext == ".md": return "markdown"
    if name.lower() == "requirements.txt": return "text"
    if ext == ".txt": return "text"
    return ""

def norm_relpath(root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(root)).replace("\\", "/")
    except Exception:
        return str(p).replace("\\", "/")

def should_skip_dir(parts: list[str], exclude_dirs: set[str]) -> bool:
    return any(part in exclude_dirs for part in parts)

def build_tree(paths: list[Path], root: Path) -> str:
    rels = sorted(norm_relpath(root, p) for p in paths)
    tree: dict = {}
    for rel in rels:
        node = tree
        for part in rel.split("/"):
            node = node.setdefault(part, {})
    lines: list[str] = []
    def render(node: dict, prefix: str = ""):
        keys = sorted(node.keys())
        for i, k in enumerate(keys):
            last = (i == len(keys) - 1)
            branch = "└── " if last else "├── "
            spacer = "    " if last else "│   "
            lines.append(prefix + branch + k)
            if isinstance(node[k], dict) and node[k]:
                render(node[k], prefix + spacer)
    render(tree, "")
    return "\n".join(lines)

# ---------- Core ----------
def collect_files(root: Path,
                  include_exts: set[str],
                  always_include_names: set[str],
                  exclude_dirs: set[str],
                  exclude_files: set[str]) -> list[Path]:
    files: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        # pular diretórios excluídos
        if should_skip_dir([part for part in p.relative_to(root).parts[:-1]], exclude_dirs):
            continue
        # pular arquivos excluídos por nome
        if p.name in exclude_files:
            continue
        # incluir por nome (sempre)
        if p.name in always_include_names:
            files.append(p)
            continue
        # incluir por extensão
        if p.suffix.lower() in include_exts or p.name.lower() == "requirements.txt":
            files.append(p)
    # remover duplicados preservando ordem
    seen = set()
    unique = []
    for f in sorted(files):
        if f not in seen:
            unique.append(f); seen.add(f)
    return unique

def write_markdown(root: Path,
                   out_path: Path,
                   files: list[Path],
                   max_bytes: int) -> None:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with out_path.open("w", encoding="utf-8", newline="\n") as w:
        w.write("# Project Snapshot\n\n")
        w.write(f"- **Root**: `{root}`\n")
        w.write(f"- **Generated**: {now}\n")
        w.write(f"- **Files included**: {len(files)}\n\n")
        w.write("## Tree (included files only)\n\n```\n")
        w.write(build_tree(files, root))
        w.write("\n```\n\n## Files\n\n")

        for p in files:
            rel = norm_relpath(root, p)
            size = p.stat().st_size
            lang = ext_to_lang(p.suffix, p.name)
            w.write(f"### {rel}\n\n> size: {size} bytes\n\n")
            if not is_textual(p):
                w.write("_skipped (binary or unreadable)_\n\n")
                continue
            try:
                data = p.read_bytes()
            except Exception as e:
                w.write(f"_error reading file: {e}_\n\n")
                continue
            clipped = False
            if max_bytes and len(data) > max_bytes:
                data = data[:max_bytes]; clipped = True
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = data.decode("utf-8", errors="replace")
            fence = lang if lang else ""
            w.write(f"```{fence}\n{text}\n```\n\n")
            if clipped:
                w.write(f"_content clipped to first {max_bytes} bytes_\n\n")

def main():
    ap = argparse.ArgumentParser(description="Dump project into a single Markdown file.")
    ap.add_argument("--root", type=str, default=".", help="pasta raiz do projeto")
    ap.add_argument("--out", type=str, default="project_dump.md", help="arquivo de saída (markdown)")
    ap.add_argument("--include", type=str, default=",".join(sorted(DEFAULT_INCLUDE)),
                    help="extensões a incluir, separadas por vírgula (ex.: .py,.yaml,.yml,.sql,.md)")
    ap.add_argument("--include-names", type=str,
                    default=",".join(sorted(DEFAULT_ALWAYS_INCLUDE_NAMES)),
                    help="nomes de arquivos a incluir SEMPRE (independente da extensão)")
    ap.add_argument("--exclude-dirs", type=str, default=",".join(sorted(DEFAULT_EXCLUDE_DIRS)),
                    help="pastas a excluir (por nome)")
    ap.add_argument("--exclude-files", type=str, default=",".join(sorted(DEFAULT_EXCLUDE_FILES)),
                    help="arquivos a excluir (por nome exato)")
    ap.add_argument("--max-bytes", type=int, default=200000,
                    help="limite de bytes por arquivo no dump (0 = sem limite)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    out_path = Path(args.out).resolve()
    include_exts = {e.strip().lower() for e in args.include.split(",") if e.strip()}
    include_names = {e.strip() for e in args.include_names.split(",") if e.strip()}
    exclude_dirs = {e.strip() for e in args.exclude_dirs.split(",") if e.strip()}
    exclude_files = {e.strip() for e in args.exclude_files.split(",") if e.strip()}
    max_bytes = int(args.max_bytes) if args.max_bytes is not None else 0

    if not root.exists():
        print(f"Root não encontrado: {root}", file=sys.stderr)
        sys.exit(1)

    files = collect_files(root, include_exts, include_names, exclude_dirs, exclude_files)
    if not files:
        print("Nenhum arquivo encontrado com os filtros atuais.", file=sys.stderr)

    write_markdown(root, out_path, files, max_bytes)
    print(f"OK: gerado {out_path}")

if __name__ == "__main__":
    main()

```

### README.md

> size: 12492 bytes

```markdown
# Offline Market Bot — Documentação do Projeto

> **Versão**: MVP (Nível 0 pronto; Níveis 1–3 planejados)  
> **Plataforma-alvo**: Windows (1440p, compatível com outras resoluções via perfis)  
> **Escopo**: *Jogo offline* com automação local **apenas** para coleta, análise e (opcionalmente) execução em UI local.  

---

## 1) Visão geral

O **Offline Market Bot** é um assistente local que **coleta preços** do mercado do jogo via **OCR da interface**, **armazena** em banco local, e oferece **visualização** (dashboard) e, nas próximas etapas, **sinais de oportunidade** (flip/refino) e **execução** (comprar/vender e logística até o baú). O projeto é organizado em **níveis** de operação para facilitar a adoção incremental:

- **Nível 0 — Coleta**: Captura e salva preços (sem sinais/execução).  
- **Nível 1 — Análise**: Calcula sinais (flip simples, bruto vs refino).  
- **Nível 2 — Execução**: Abre ordens de compra/venda e controla ordens/estoque.  
- **Nível 3 — Logística**: Move itens entre **loja ↔ baú**.

O MVP entregue foca no **Nível 0**, com comandos para **varrer** a UI do mercado, **persistir** no **SQLite** e **visualizar/exportar** no **Streamlit**. Já há esqueleto para buscar itens por **campo de pesquisa** (digitação) antes de ler a lista de preços.

---

## 2) Objetivos do projeto

1. **Construir um pipeline local** e robusto de captura de preços do mercado do jogo (OCR + rolagem/scroll).  
2. **Persistir os dados** com integridade (deduplicação, índices, auditoria básica).  
3. **Dar visibilidade rápida** com um **dashboard** simples e exportação CSV.  
4. Evoluir para **detecção de flips** (spread pós-taxas) e **decisões sobre refino** (quando ativado).  
5. Opcionalmente **executar** (comprar/vender) e **mover** itens entre loja e baú, com limites e logs de auditoria.  

---

## 3) Como funciona (alto nível)

1. **Captura da janela**: O bot identifica a **janela do jogo em foco** (ou por processo/título, conforme configuração) e captura **apenas** aquela região, não a tela inteira.  
2. **Recortes relativos (anchors)**: Áreas como **campo de busca**, **lista do book**, **colunas (nome/preço/qty)** são definidas por **proporções** no arquivo `config/ui_profiles.yaml`.  
3. **OCR**: O texto e os números são extraídos com **PaddleOCR** (primário) ou **Tesseract** (fallback). O parser aplica regex de preço e limiar de confiança.  
4. **Scroll**: A lista é lida por “blocos” (linhas visíveis), e o bot pode avançar o **scroll** entre blocos (no Nível 0, o scroll é básico; você escolhe quantas “páginas” quer ler com `--pages`).  
5. **Persistência**: Os resultados são gravados em **SQLite** (`data/market.db`) nas tabelas `runs` e `prices_snapshots`.  
6. **Visualização**: O **Streamlit** exibe o que foi coletado, com filtros e **exportação CSV**.  
7. **(Opcional no Nível 0)**: O bot pode **digitar o nome do item no campo de busca** para abrir o book correto antes de capturar (ver comando `scan_watchlist`).  

---

## 4) Arquitetura do sistema

```
[Janela do Jogo]
   │  (Win32 capture + recortes relativos + scroll)
   ▼
[OCR]
   ├─ PaddleOCR (primário, CPU)
   └─ Tesseract (fallback)
   │
   ▼
[Parser & Normalizer]
   ├─ Regex de preço, limpeza de texto
   └─ Dedup + score de confiança
   │
   ▼
[Storage: SQLite]
   ├─ prices_snapshots, runs
   └─ (futuro) order_book, my_orders, inventory, fees, recipes, logs
   │
   ▼
[UI]
   ├─ Overlay (futuro: hotkeys/status/sinais)
   └─ Streamlit (dashboard + export CSV)
   │
   ▼
[Executor (futuro)]
   ├─ Navegação por busca/categorias
   ├─ Comprar/Vender com confirmação
   └─ Logística Loja ↔ Baú
```

**Stack (MVP):** Python 3.11+, OpenCV, PaddleOCR/Tesseract, SQLModel/SQLite, Streamlit, pywin32, keyboard, Typer CLI.  
**Automação futura (Nível 2/3):** AutoHotkey (AHK v2) orquestrado por Python + anchors.

---

## 5) Estrutura de pastas

```
offline-market-bot/
├─ README.md
├─ requirements.txt
├─ schema.sql
├─ .env.example
├─ config/
│  ├─ ui_profiles.yaml     # perfis de âncoras e colunas por resolução/DPI
│  ├─ ocr.yaml             # ajustes dos engines e regex de preço
│  └─ capture.yaml         # como selecionar a janela (processo/foreground/título)
├─ data/
│  ├─ market.db            # SQLite (gerado no primeiro run)
│  ├─ screenshots/         # (opcional) imagens de teste
│  └─ watchlist.csv        # (opcional) lista de itens a consultar por busca
├─ src/
│  ├─ main.py              # CLI: scan, dashboard, scan_watchlist
│  ├─ storage/db.py
│  ├─ ocr/engine.py
│  ├─ ocr/extract.py
│  ├─ capture/window.py
│  ├─ capture/calibrate.py
│  ├─ exec/nav.py          # (opcional Nível 0) digitar no campo de busca
│  └─ utils/logging.py
└─ streamlit_app.py
```

---

## 6) Instalação rápida

1. **Python & venv**
```bash
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

2. **OCR**
- **Tesseract (recomendado c/ fallback)**: instale no Windows e aponte `config/ocr.yaml:tesseract.path` (ex.: `C:\Program Files\Tesseract-OCR\tesseract.exe`).  
- **PaddleOCR**: funciona como primário; se preferir só Tesseract, deixe `engine_order: ["tesseract"]` em `ocr.yaml`.

3. **Banco**
```bash
# É criado automaticamente no primeiro run
sqlite3 data/market.db ".tables"  # (opcional) checar se criou
```

---

## 7) Configuração

### 7.1 `config/capture.yaml`
```yaml
window_select:
  mode: foreground_process     # foreground_process | title_match | whole_screen
  process_name: "SEU_JOGO.exe" # nome do executável
  title_contains: ""           # usado se mode=title_match
max_pages: 50
retry:
  ocr_max_retries: 2
  ocr_retry_delay_ms: 120
```

### 7.2 `config/ui_profiles.yaml` (exemplo 1440p@100%)
```yaml
profiles:
  "2560x1440@100%":
    anchors:
      market_title: {x: 0.50, y: 0.08, w: 0.20, h: 0.05}
      search_box:   {x: 0.25, y: 0.12, w: 0.30, h: 0.05}
      results_zone: {x: 0.25, y: 0.17, w: 0.50, h: 0.30}
      list_zone:    {x: 0.10, y: 0.22, w: 0.80, h: 0.66}
      footer_zone:  {x: 0.10, y: 0.90, w: 0.80, h: 0.06}
    columns:
      name:  {x: 0.02, w: 0.50}
      price: {x: 0.58, w: 0.20}
      qty:   {x: 0.80, w: 0.18}
    scroll:
      step_pixels: 240
      pause_ms: 150
```

> **Dica**: Os valores são **proporcionais** à janela (0–1). Ajuste com capturas e tente manter o `list_zone` cobrindo exatamente a grade do book.

### 7.3 `config/ocr.yaml`
```yaml
engine_order: ["paddle", "tesseract"]
tesseract:
  path: "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
  psm: 6
  oem: 3
  whitelist: "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,-% "
postprocess:
  price_regex: "(\\d+(?:[\\.,]\\d{1,2})?)"
  min_confidence: 0.65
```

### 7.4 `data/watchlist.csv` (opcional)
```
item_name
Ferro Bruto
Ferro Refinado
Barra de Aço
```

---

## 8) Esquema de dados (Nível 0)

```sql
CREATE TABLE runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  mode TEXT NOT NULL,
  notes TEXT
);

CREATE TABLE prices_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  timestamp TEXT NOT NULL,
  source_view TEXT NOT NULL,        -- 'BUY_LIST' | 'SELL_LIST'
  item_name TEXT NOT NULL,
  price REAL NOT NULL,
  qty_visible INTEGER,
  page_index INTEGER,
  scroll_pos REAL,
  confidence REAL,
  hash_row TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
```

> **Futuro (Níveis 1–3)**: `order_book`, `my_orders`, `inventory`, `fees`, `crafting_recipes`, `signals`, `actions_log` etc.

---

## 9) Fluxos e comandos

### 9.1 Coleta simples (Nível 0)
- **Pré-requisito**: Abra o **market** no jogo (compra **ou** venda) e deixe a lista visível.  
- **Executar**:
```bash
python -m src.main scan --source-view BUY_LIST --pages 3
```
> Lê ~12 linhas por “página”. Ajuste `--pages` conforme o tamanho real da lista/scroll.

### 9.2 Varrer watchlist (digitando no campo de busca)
```bash
python -m src.main scan_watchlist --source-view BUY_LIST --watchlist-csv data/watchlist.csv
```
> Para cada `item_name`, o bot clica no `search_box`, **digita**, abre o item e **captura** a lista.

### 9.3 Dashboard (visualização e export)
```bash
python -m src.main dashboard
```
Acesse o link local (normalmente `http://localhost:8501`) para filtrar e **Exportar CSV**.

---

## 10) Roadmap (resumo)

- **Nível 1**: order_book consolidado (best bid/ask), **sinais de flip** pós-taxas, ranking por EV/liquidez, aba “Sinais” no Streamlit.  
- **Nível 2**: executor (AHK v2) para **comprar/vender** de forma segura (confirmações, slippage, limites, kill-switch), tracking de **my_orders** e PnL.  
- **Nível 3**: logística **Loja ↔ Baú**, controle de estoque (`inventory`), recomendações “**o que fazer com meus itens**” (bruto vs refino).

---

## 11) KPIs (quando ativar Nível 1+)

- **Precision@K** dos sinais (% de flips lucrativos).  
- **EV Realizado / EV Previsto** (calibração).  
- **Tempo**: scan → sinal → execução.  
- **Erro OCR**: % de linhas descartadas/corrigidas.  
- **ROI** por categoria de item.

---

## 12) Política operacional (quando ativar execução)

- **Modos**: `SCAN` (só coleta), `SIGNAL` (gera oportunidades), `EXEC` (executa fila).  
- **Limites**: cliques/min, pausas humanas (100–250ms), **cap** de qty e valor por ordem/sessão.  
- **Kill-switch**: hotkey global para abortar (ex.: `F10`).  
- **Sandbox**: confirmações duplas; sem ordens reais.

---

## 13) Riscos & Mitigações

- **Mudança de UI / patch** → perfis de UI por resolução/DPI + fallback de OCR + calibração guiada.  
- **Erro de OCR** → dupla leitura/regex/limiar de confiança; descartar outliers e reler.  
- **DPI/escala** → coordenadas **proporcionais**; perfis nomeados por resolução@escala.  
- **Misclick/scroll desajustado** (Nível 2/3) → verificação pós-ação por âncoras (ícone/label), timeouts e retries.  
- **Falsos positivos de preço** → validações (preço com 2 casas decimais, faixa esperada, consistência entre linhas).

---

## 14) Solução de problemas (FAQ rápido)

- **“Não apareceu nada no dashboard.”**  
  Verifique: (a) janela correta foi capturada (process_name/título), (b) `ui_profiles.yaml` cobre a área **exata** da lista, (c) OCR está instalado (Tesseract/Paddle), (d) `--pages` suficiente.

- **“Números saem errados.”**  
  Ajuste `price_regex` e `whitelist`; garanta idioma/teclado correto; melhore contraste/zoom do jogo.

- **“Em 125% de escala do Windows, erra os recortes.”**  
  Crie um perfil `2560x1440@125%` com âncoras recalibradas e deixe esse perfil **primeiro** no YAML.

- **“O bot digitou, mas não abriu o item.”**  
  Ajuste `results_zone` para clicar no resultado; se o jogo abre direto, remova o clique extra.

---

## 15) Licença & créditos

- **Licença**: MIT (padrão; ajuste conforme sua preferência).  
- **Créditos**: Projeto e implementação local para jogo **offline**, sem integração online.

---

## 16) Glossário

- **Anchor (âncora)**: retângulo relativo (x,y,w,h 0–1) usado como referência de clique/captura.  
- **Book**: lista de ordens de compra/venda para um item.  
- **EV (Expected Value)**: valor esperado de lucro após custos.  
- **OCR**: reconhecimento ótico de caracteres.  
- **WAL (SQLite)**: modo de journaling que melhora concorrência e robustez.

---

## 17) Referência de comandos (MVP)

```bash
# Coleta simples na tela atual (Nível 0)
python -m src.main scan --source-view BUY_LIST --pages 3

# Coleta digitando itens de uma watchlist (Nível 0)
python -m src.main scan_watchlist --source-view BUY_LIST --watchlist-csv data/watchlist.csv

# Dashboard (Nível 0)
python -m src.main dashboard
```

---

**Dúvidas?** Abra uma *issue* no seu repositório ou descreva a tela (resolução, print do market). Posso devolver um `ui_profiles.yaml` já calibrado.


```

### requirements.txt

> size: 320 bytes

```text
# paddleocr==2.7.0.3  # desativado no Windows p/ evitar conflito com OpenCV 4.10
pytesseract==0.3.10
opencv-python==4.10.0.84
numpy==1.26.4
Pillow==10.4.0
pywin32==306
keyboard==0.13.5
typer==0.12.5
sqlalchemy==2.0.36
sqlmodel==0.0.22
python-dotenv==1.0.1
structlog==24.1.0
streamlit==1.38.0
pandas==2.2.2

```

### schema.sql

> size: 814 bytes

```sql
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  mode TEXT NOT NULL,               -- 'scan'
  notes TEXT
);

CREATE TABLE IF NOT EXISTS prices_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  timestamp TEXT NOT NULL,
  source_view TEXT NOT NULL,        -- 'BUY_LIST' | 'SELL_LIST'
  item_name TEXT NOT NULL,
  price REAL NOT NULL,
  qty_visible INTEGER,
  page_index INTEGER,
  scroll_pos REAL,
  confidence REAL,
  hash_row TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_prices_item_time ON prices_snapshots(item_name, timestamp);
CREATE INDEX IF NOT EXISTS idx_prices_source ON prices_snapshots(source_view);

```

### src/__init__.py

> size: 0 bytes

```python

```

### src/capture/__init__.py

> size: 0 bytes

```python

```

### src/capture/calibrate.py

> size: 238 bytes

```python
from .window import get_screen_resolution


def relative_rect(rel, screen):
    sw, sh = screen
    return (
        int(rel["x"] * sw),
        int(rel["y"] * sh),
        int(rel["w"] * sw),
        int(rel["h"] * sh),
    )

```

### src/capture/window.py

> size: 2151 bytes

```python
import ctypes
import time
from typing import Dict, Optional, Tuple

from PIL import ImageGrab
import win32gui


def get_screen_resolution() -> Tuple[int, int]:
    """Return the current screen resolution as ``(width, height)``."""

    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def capture_rect(x: int, y: int, w: int, h: int):
    """Capture a rectangular region of the screen specified in absolute pixels."""

    bbox = (x, y, x + w, y + h)
    return ImageGrab.grab(bbox=bbox)


def human_pause(ms: int = 120) -> None:
    """Pause execution for a short human-like delay expressed in milliseconds."""

    time.sleep(ms / 1000)


def _rect_to_xywh(rect: Tuple[int, int, int, int]) -> Dict[str, int]:
    """Convert a Windows rect tuple (left, top, right, bottom) into an ``x, y, w, h`` mapping."""

    left, top, right, bottom = rect
    return {"x": left, "y": top, "w": right - left, "h": bottom - top}


def get_window_rect(title_contains: str) -> Optional[Dict[str, object]]:
    """Return the bounding box for the first visible window whose title contains the given text."""

    target = {"handle": None, "title": None, "rect": None}

    def enum_handler(hwnd, ctx):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd) or ""
        if title_contains.lower() in title.lower():
            rect = win32gui.GetWindowRect(hwnd)
            ctx["handle"] = hwnd
            ctx["title"] = title
            ctx["rect"] = rect

    win32gui.EnumWindows(enum_handler, target)

    if target["rect"]:
        rect_xywh = _rect_to_xywh(target["rect"])
        return {
            "x": rect_xywh["x"],
            "y": rect_xywh["y"],
            "w": rect_xywh["w"],
            "h": rect_xywh["h"],
            "title": target["title"],
        }

    return None


def capture_rect_in_window(wx: int, wy: int, x: int, y: int, w: int, h: int):
    """Capture a rectangle relative to a window's top-left corner."""

    return capture_rect(wx + x, wy + y, w, h)

```

### src/main.py

> size: 1642 bytes

```python
import json
from pathlib import Path

import typer

from src.ocr.extract import scan_once
from src.storage.db import end_run, ensure_db, insert_snapshot, new_run

app = typer.Typer(add_completion=False)

BASE = Path(__file__).resolve().parents[1]
CFG_OCR = BASE / "config" / "ocr.yaml"
CFG_UI = BASE / "config" / "ui_profiles.yaml"


@app.command()
def scan(
    source_view: str = typer.Option("BUY_LIST", help="BUY_LIST ou SELL_LIST"),
    pages: int = typer.Option(3, help="quantas páginas (scrolls) estimar"),
    out_json: str = typer.Option("", help="salvar também em JSON (opcional)"),
):
    """Nível 0: captura uma amostra da lista (12 linhas por página) e salva no SQLite."""
    con = ensure_db()
    run_id = new_run(con, mode="scan", notes=f"{source_view}")
    all_rows = []
    try:
        for p in range(pages):
            rows = scan_once(
                source_view,
                str(CFG_OCR),
                str(CFG_UI),
                page_index=p,
                scroll_pos=p,
            )
            for r in rows:
                insert_snapshot(con, run_id, r)
            all_rows.extend(rows)
        if out_json:
            Path(out_json).write_text(
                json.dumps(all_rows, indent=2), encoding="utf-8"
            )
    finally:
        end_run(con, run_id)


@app.command()
def dashboard():
    """Abre o dashboard Streamlit (Nível 0)."""
    import subprocess
    import sys

    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(BASE / "streamlit_app.py")]
    )


if __name__ == "__main__":
    app()

```

### src/ocr/__init__.py

> size: 0 bytes

```python

```

### src/ocr/engine.py

> size: 1733 bytes

```python
import re

import numpy as np
from PIL import Image
import yaml

try:
    from paddleocr import PaddleOCR
except Exception:  # pragma: no cover - optional dependency
    PaddleOCR = None

import pytesseract

PRICE_RE = None
MIN_CONF = 0.65


def load_ocr_config(path_ocr_yaml: str):
    """Load OCR configuration file and set global parameters."""
    global PRICE_RE, MIN_CONF
    with open(path_ocr_yaml, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    PRICE_RE = re.compile(cfg["postprocess"]["price_regex"])
    MIN_CONF = float(cfg["postprocess"]["min_confidence"])
    tess_cfg = cfg.get("tesseract", {})
    if tess_cfg.get("path"):
        pytesseract.pytesseract.tesseract_cmd = tess_cfg["path"]
    return cfg


class OCREngine:
    def __init__(self, cfg):
        self.cfg = cfg
        self.paddle = None
        if "paddle" in cfg.get("engine_order", []) and PaddleOCR is not None:
            self.paddle = PaddleOCR(
                use_angle_cls=False,
                use_gpu=False,
                det=True,
                rec=True,
                lang="en",
            )

    def text_and_conf(self, img: Image.Image) -> tuple[str, float]:
        # 1) Paddle
        if self.paddle:
            res = self.paddle.ocr(np.array(img), cls=False)
            if res and res[0]:
                # pega a linha com melhor confiança média
                best = max(res[0], key=lambda r: float(r[1][1]))
                return best[1][0], float(best[1][1])
        # 2) Tesseract fallback
        txt = pytesseract.image_to_string(
            img, config=f'--psm {self.cfg["tesseract"]["psm"]}'
        )
        return txt.strip(), 0.60

```

### src/ocr/extract.py

> size: 2701 bytes

```python
from datetime import datetime
import hashlib
from typing import Dict, List

import yaml

from ..capture.window import capture_rect, get_screen_resolution
from ..capture.calibrate import relative_rect
from .engine import MIN_CONF, PRICE_RE, OCREngine, load_ocr_config


def parse_price(text: str):
    if PRICE_RE is None:
        return None
    m = PRICE_RE.search(text.replace(" ", ""))
    if not m:
        return None
    raw = m.group(1).replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except Exception:
        return None


def scan_once(
    source_view: str,
    ocr_cfg_path: str,
    ui_cfg_path: str,
    page_index: int = 0,
    scroll_pos: float = 0.0,
) -> List[Dict]:
    with open(ui_cfg_path, "r", encoding="utf-8") as fh:
        ui = yaml.safe_load(fh)
    prof = next(iter(ui["profiles"].values()))  # pega primeiro perfil como default
    cols = prof["columns"]
    screen = get_screen_resolution()

    list_zone = relative_rect(prof["anchors"]["list_zone"], screen)
    lx, ly, lw, lh = list_zone

    engine = OCREngine(load_ocr_config(ocr_cfg_path))

    rows: List[Dict] = []
    # Exemplo simples: amostra 12 linhas verticais
    line_h = int(lh / 12)
    for i in range(12):
        y0 = ly + i * line_h
        # recorte de nome
        name_rect = (
            lx + int(cols["name"]["x"] * lw),
            y0,
            int(cols["name"]["w"] * lw),
            line_h,
        )
        name_img = capture_rect(*name_rect)
        name_txt, conf_name = engine.text_and_conf(name_img)

        # recorte de preço
        price_rect = (
            lx + int(cols["price"]["x"] * lw),
            y0,
            int(cols["price"]["w"] * lw),
            line_h,
        )
        price_img = capture_rect(*price_rect)
        price_txt, conf_price = engine.text_and_conf(price_img)
        price_val = parse_price(price_txt)

        if price_val is None or max(conf_name, conf_price) < MIN_CONF:
            continue

        item_name = " ".join(name_txt.split())
        h = hashlib.sha1(
            f"{item_name}|{price_val}|{i}|{page_index}".encode()
        ).hexdigest()
        rows.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "source_view": source_view,
                "item_name": item_name,
                "price": price_val,
                "qty_visible": None,
                "page_index": page_index,
                "scroll_pos": scroll_pos,
                "confidence": float(min(conf_name, conf_price)),
                "hash_row": h,
            }
        )
    return rows

```

### src/storage/__init__.py

> size: 0 bytes

```python

```

### src/storage/db.py

> size: 1462 bytes

```python
from pathlib import Path
import sqlite3

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema.sql"
DB_PATH = Path(__file__).resolve().parents[2] / "data" / "market.db"


def ensure_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        con.executescript(f.read())
    con.commit()
    return con


def new_run(con, mode="scan", notes=None):
    cur = con.cursor()
    cur.execute(
        "INSERT INTO runs (started_at, mode, notes) VALUES (datetime('now'), ?, ?)",
        (mode, notes),
    )
    con.commit()
    return cur.lastrowid


def end_run(con, run_id):
    con.execute("UPDATE runs SET ended_at=datetime('now') WHERE run_id=?", (run_id,))
    con.commit()


def insert_snapshot(con, run_id, row):
    con.execute(
        """
        INSERT INTO prices_snapshots
        (run_id, timestamp, source_view, item_name, price, qty_visible, page_index, scroll_pos, confidence, hash_row)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            run_id,
            row["timestamp"],
            row["source_view"],
            row["item_name"],
            row["price"],
            row.get("qty_visible"),
            row.get("page_index"),
            row.get("scroll_pos"),
            row.get("confidence"),
            row.get("hash_row"),
        ),
    )
    con.commit()

```

### src/utils/logging.py

> size: 454 bytes

```python
import structlog
import logging
import sys


def setup_logging():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.processors.add_timestamp,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger()

```

### streamlit_app.py

> size: 1266 bytes

```python
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

```

