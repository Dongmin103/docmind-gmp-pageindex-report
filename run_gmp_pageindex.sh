#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3.11 -m venv .venv
fi

source .venv/bin/activate

# PageIndex requires an LLM provider via LiteLLM. Put OPENAI_API_KEY in PageIndex/.env
# or export it before running this script.
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

if [ -z "${OPENAI_API_KEY:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -z "${GEMINI_API_KEY:-}" ] && [ -z "${GOOGLE_API_KEY:-}" ]; then
  echo "ERROR: No LLM API key found. Create PageIndex/.env with OPENAI_API_KEY=... or export a supported LiteLLM provider key." >&2
  exit 2
fi

PDF_PATH="inputs/gmp_guidance.pdf"
if [ ! -f "$PDF_PATH" ]; then
  echo "ERROR: PDF not found: $PDF_PATH" >&2
  exit 3
fi

python run_pageindex.py \
  --pdf_path "$PDF_PATH" \
  --model "${PAGEINDEX_MODEL:-gpt-4o-mini}" \
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
