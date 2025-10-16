# Offline Market Bot — Nível 0

Ferramenta mínima para capturar preços de uma lista do jogo *New World* usando OCR local.

## Requisitos

- Python 3.10+
- Tesseract OCR instalado e disponível no PATH (ou configure `config/ocr.yaml`).
- Opcional: [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) para melhor reconhecimento.

Instale as dependências com:

```bash
pip install -r requirements.txt
```

## Captura (CLI)

Execute uma captura simples (12 linhas por página) com:

```bash
python -m src.main scan --source-view BUY_LIST --pages 3 --out-json amostra.json
```

Os resultados são armazenados em `data/market.db`. Para abrir o dashboard:

```bash
python -m src.main dashboard
```

## Dashboard

O dashboard Streamlit mostra a tabela com os dados coletados e permite exportar um CSV.
