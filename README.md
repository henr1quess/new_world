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

## 6.1) Calibração (definir regiões sem “olhar a olho”)
1. Abra o jogo no **market** (modo janela/borderless).
2. Ajuste `config/capture.yaml: window_title_contains` para algo que exista no título da janela.
3. Rode o calibrador e siga as janelas de seleção:
   ```bash
   python -m src.tools.calibrate_ui
   ```
   Ele pedirá, na ordem: `search_box`, `results_zone`, `buy_tab`, `sell_tab`, `header_row`, `list_zone`, `footer_zone` e as colunas `name`, `price`, `qty`.  
   O resultado é salvo em `config/ui_profiles.yaml` como proporções da **janela**.

4. (Opcional) Teste o OCR numa área à sua escolha:
   ```bash
   python -m src.tools.ocr_probe
   ```

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

### 9.4 Jobs (sequências automatizadas)
- Defina um arquivo YAML com uma lista de jobs, ex.: `jobs.yaml`.
- Tipos suportados:
  - `collect_watchlist`: abre itens (via `open_item`) e coleta BUY/SELL.
  - `collect_category`: navega por uma categoria pré-configurada e cadastra itens.
- Execute:
  ```bash
  python -m src.main jobs --jobs-file jobs.yaml
  ```
- O scheduler garante que a janela monitorada está ativa antes de iniciar cada job.

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

