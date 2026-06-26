#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3.11 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip
  pip install --upgrade -r requirements.txt --use-deprecated=legacy-resolver
else
  source .venv/bin/activate
fi

PDF_PATH="inputs/gmp_guidance.pdf"
if [ ! -f "$PDF_PATH" ]; then
  echo "ERROR: PDF not found: $PDF_PATH" >&2
  exit 3
fi

# Use the local Codex CLI OAuth/session instead of LiteLLM API keys.
export PAGEINDEX_LLM_BACKEND="${PAGEINDEX_LLM_BACKEND:-codex}"
export PAGEINDEX_CODEX_TIMEOUT="${PAGEINDEX_CODEX_TIMEOUT:-600}"

python run_pageindex.py \
  --pdf_path "$PDF_PATH" \
  --model codex \
  --toc-check-pages "${PAGEINDEX_TOC_CHECK_PAGES:-30}" \
  --max-pages-per-node "${PAGEINDEX_MAX_PAGES_PER_NODE:-10}" \
  --max-tokens-per-node "${PAGEINDEX_MAX_TOKENS_PER_NODE:-20000}" \
  --if-add-node-id yes \
  --if-add-node-summary "${PAGEINDEX_ADD_NODE_SUMMARY:-yes}" \
  --if-add-doc-description "${PAGEINDEX_ADD_DOC_DESCRIPTION:-no}" \
  --if-add-node-text "${PAGEINDEX_ADD_NODE_TEXT:-no}"

python - <<'PY'
import json
from pathlib import Path
out = Path('results/gmp_guidance_structure.json')
print(f'output_exists={out.exists()} path={out}')
if out.exists():
    data = json.loads(out.read_text(encoding='utf-8'))
    if isinstance(data, dict):
        print('top_level_keys=', sorted(data.keys()))
        print('child_count=', len(data.get('nodes', [])))
    elif isinstance(data, list):
        print('top_level_list_count=', len(data))
PY
