You are running a CLEAN PageIndex-style agentic retrieval batch.

Repository: /Users/dongmin/Documents/myproject/DocMIND/PageIndex
Working directory: /Users/dongmin/Documents/myproject/DocMIND/PageIndex

STRICT NO-GOLD RULE:
- Do NOT read eval/gmp_eval_testset.jsonl.
- Do NOT read any score_*.json/md, page_misses.json, generation_trace, or previous predictions under results/codex_retriever_10x10.
- Use only this question-only file as the question source:
  results/codex_agentic_10x10/questions_001_010.jsonl
- Do not use fields named gold_pages, gold_section_path, expected_answer, retrieval_target, answer_judging_notes.

Use the PageIndex repo retrieval flow exactly:
1. Call/get document metadata first using:
   .venv/bin/python scripts/gmp_pageindex_codex_retriever.py tool document
2. Call/get document structure using:
   .venv/bin/python scripts/gmp_pageindex_codex_retriever.py tool structure --max-depth 4
   You may also query focused structure snippets, e.g.:
   .venv/bin/python scripts/gmp_pageindex_codex_retriever.py tool structure --query '용어의 정의' --max-depth 4
3. For each question, reason about the question intent and choose candidate section/page(s).
4. Call get_page_content with tight ranges only, e.g.:
   .venv/bin/python scripts/gmp_pageindex_codex_retriever.py tool page --pages '18'
   You may call multiple tight ranges per question if needed.
5. Write final predictions JSONL only to:
   results/codex_agentic_10x10/predictions_001_010_agentic.jsonl

Output JSONL schema, one row per question:
{"id":"gmp_eval_001","question":"copied exactly","predicted_section_path":["tree","path"],"predicted_pages":"tight page(s)","evidence_pages_read":"pages you actually inspected","reason":"brief retrieval rationale based on tree/page content"}

Important retrieval heuristics are allowed only as reasoning, not gold lookup:
- If the question asks 정의/무엇을 의미/정의상, inspect 용어의 정의 first.
- If the question asks 누구/책임자/승인 책임, inspect 조직/품질(보증)부서 책임자 first.
- If comparison asks two terms, inspect the definition section and read pages containing both terms.
- Never fetch the whole document.

After writing the JSONL, run:
.venv/bin/python scripts/gmp_pageindex_codex_retriever.py validate-predictions results/codex_agentic_10x10/predictions_001_010_agentic.jsonl

Final answer: concise summary only. Do not include gold labels.
