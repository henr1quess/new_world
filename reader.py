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
    for f in files:
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
            try:
                size = p.stat().st_size
            except Exception:
                size = 0
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
