#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
if ! "$PYTHON_BIN" -c 'import streamlit' >/dev/null 2>&1; then
  echo "Streamlit is not installed for $PYTHON_BIN." >&2
  echo "Install dependencies first: $PYTHON_BIN -m pip install -r requirements.txt" >&2
  exit 1
fi
exec "$PYTHON_BIN" -m streamlit run apps/gmp_pageindex_ui.py "$@"
