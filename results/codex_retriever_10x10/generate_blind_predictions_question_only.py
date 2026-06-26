#!/usr/bin/env python3
from __future__ import annotations
import json, math, re
from pathlib import Path
from collections import Counter, defaultdict

EVAL=Path('eval/gmp_eval_testset.jsonl')
DOC=Path('results/pageindex_gmp_workspace/gmp-guidance.json')
OUTDIR=Path('results/codex_retriever_10x10')
OUTDIR.mkdir(parents=True, exist_ok=True)

doc=json.loads(DOC.read_text(encoding='utf-8'))
pages={int(p['page']): p.get('content','') for p in doc['pages']}
structure=doc['structure']

def norm(s):
    return re.sub(r'\s+',' ',str(s or '')).strip()

def compact(s):
    return re.sub(r'\s+','',str(s or '')).lower()

STOP=set('''무엇 어떤 어떻게 하는 하여야 하며 한다 된다 있는 없는 경우 관련 기준 문서 항목 의약품 제조 품질 관리 제품 완제품 원자재 작업소 작업 작업원 기준서 사항 절차 기록 보관 구분 실시 하여 대한 및 또는 에서 으로 하고 한다면'''.split())
SUFFIXES=['하여야','하여','하는','한다','된다','되어','하며','하고','까지','부터','에서','으로','에게','에는','로서','로써','들을','으로서','으로써','과의','와의','관한','관련','의','을','를','이','가','은','는','에','와','과','도','만']
def strip_suffix(tok):
    tok=tok.lower().strip()
    changed=True
    while changed:
        changed=False
        for suf in SUFFIXES:
            if tok.endswith(suf) and len(tok)>len(suf)+1:
                tok=tok[:-len(suf)]
                changed=True
                break
    return tok

def tokens(s):
    raw=re.findall(r'[가-힣A-Za-z0-9]{2,}', str(s or '').lower())
    out=[]
    for t in raw:
        t=strip_suffix(t)
        if t and t not in STOP and len(t)>=2:
            out.append(t)
    return out

# question-driven alias expansion; no gold labels used.
ALIASES={
 '일탈':['일탈','기준일탈'], '기준일탈':['기준일탈','일탈'], '밸리데이션':['밸리데이션','검증','문서화'],
 '컴퓨터화':['컴퓨터화','computerized','system','시스템'], '시스템':['시스템','system'], '전주기':['전주기','life cycle','수명주기'],
 '청정구역':['청정구역','부유입자','미생물'], '무균구역':['무균구역','무균작업','무균물질','밀봉','무균시험'],
 '세척':['세척','세제','소독제','세척 밸리데이션'], '제조용수':['제조용수','필요한 질과 양'],
 '하수구':['하수구','역류','소독'], '공기조화장치':['공기조화장치','차압','청정등급'], '차압':['차압','공기조화'],
 '자동화장치':['자동화장치','자료 유실','대체 시스템','기록 변경'], '기록문서':['기록문서','전자기록','보존'],
 '작업복':['작업복','갱의','착용'], '보관':['보관','구분','선입선출'], '출고':['출고','선입선출','출하'],
 '안정성시험':['안정성','사용기간','유효기간'], '포장재료':['포장재료','접촉','적합'], '교정':['교정','적격성평가'],
 '무균제제':['무균제제','무균','제균','밀봉검사'], '검체':['검체','채취','오염방지'], '고장':['고장','사용하지 않는','표시'],
 '중요':['중요 기계','중요공정','교정','적격성평가'], '반입':['반입','적합판정','검체 채취'], '수율':['수율','실생산량','이론 생산량'],
 '포장작업':['포장작업','표시재료','포장'], '회수':['회수','유통된 모든 국가','관계 당국'], '불만':['불만','소비자','원인','재발방지'],
 '변경':['변경관리','영향','밸리데이션','안정성 시험'], '자율점검':['자율점검','자체적','보고서'], '교육':['교육','훈련','평가','재교육'],
 '출하':['출하','출하 승인','시험성적서','제조기록서'], '전자':['전자','데이터','백업','접근성'], '데이터':['데이터','백업','점검기록','ALCOA'],
 '반품':['반품','재입고','재포장'], '품질보증':['품질보증','품질관리','품질평가'], '품질평가':['제품품질평가','품질평가'],
 'ALCOA':['ALCOA','Attributable','Legible','Contemporaneous','Original','Accurate'], 'Audit':['Audit Trail','점검기록'],
 '재포장':['재포장','표시','사용기한'], '재가공':['재가공','기준일탈','반제품'], '위탁':['위탁','수탁','계약'],
}

def expand_terms(q):
    ts=tokens(q)
    extra=[]
    cq=compact(q)
    for k, vals in ALIASES.items():
        if compact(k) in cq or any(compact(v) in cq for v in vals):
            extra.extend(vals)
    # quoted exact terms are high signal
    quoted=re.findall(r"['‘’\"]([^'‘’\"]{2,40})['‘’\"]", q)
    extra.extend(quoted)
    return ts + tokens(' '.join(extra)) + [e.lower() for e in extra if re.search(r'[A-Za-z]', e)]

page_toks={p:tokens(c) for p,c in pages.items()}
df=Counter()
for p,ts in page_toks.items():
    for t in set(ts): df[t]+=1
N=len(pages)

def page_score(q, p):
    qterms=expand_terms(q)
    cnt=Counter(page_toks[p])
    text=compact(pages[p])
    score=0.0
    for t in qterms:
        nt=strip_suffix(t)
        if not nt: continue
        tf=cnt.get(nt,0)
        if tf:
            score += (1+math.log(tf))*math.log((N+1)/(1+df.get(nt,0))+1)
        ct=compact(t)
        if len(ct)>=3 and ct in text:
            score += 3.0
    # quoted exact phrase strong bonus
    for phrase in re.findall(r"['‘’\"]([^'‘’\"]{2,40})['‘’\"]", q):
        if compact(phrase) in text: score += 10.0
    return score

def flatten(nodes,path=()):
    out=[]
    for n in nodes:
        cur=path+(str(n.get('title','')),)
        out.append((cur,n))
        out.extend(flatten(n.get('nodes') or [],cur))
    return out
nodes=flatten(structure)

def page_range(n):
    s=int(n.get('start_index') or n.get('own_start_index') or 1); e=int(n.get('end_index') or n.get('own_end_index') or s); return s,e

def subtree_range(n):
    s=int(n.get('subtree_start_index') or n.get('start_index') or 1); e=int(n.get('subtree_end_index') or n.get('end_index') or s); return s,e

def node_score(q,path,n,pred_pages):
    qterms=set(expand_terms(q))
    title=' > '.join(path)
    tt=set(tokens(title))
    score=len(qterms & tt)*5.0
    ctitle=compact(title); cq=compact(q)
    for t in qterms:
        if compact(t) and compact(t) in ctitle: score += 4.0
    for part in path:
        cp=compact(part)
        if cp and cp in cq: score += 6.0
    own_s,own_e=page_range(n); sub_s,sub_e=subtree_range(n)
    if any(own_s<=p<=own_e for p in pred_pages): score += 5.0
    if all(sub_s<=p<=sub_e for p in pred_pages): score += 2.0
    span=sub_e-sub_s+1
    score -= min(span,200)*0.01
    # prefer semantic parent sections over one-line long leaf definitions for general definition questions
    if '정의' in q and len(path)>=2 and '용어의 정의' in path[-1]: score += 12
    if '정의' in q and len(path)>=3 and '용어의 정의' in path[-2]: score += 10
    return score

def choose_pages(q):
    ranked=sorted(((page_score(q,p),p) for p in pages), reverse=True)
    # choose top page plus adjacent page if close and contiguous for multi-hop/procedure questions
    top_score, top=ranked[0]
    selected=[top]
    for s,p in ranked[1:8]:
        if s <= 0: continue
        if abs(p-top)<=1 and s >= top_score*0.55:
            selected.append(p)
    selected=sorted(set(selected))
    # avoid over-broad; max 3 contiguous-ish pages
    selected=selected[:3]
    return selected, ranked[:8]

def pages_to_str(ps):
    ps=sorted(set(ps)); chunks=[]
    if not ps: return ''
    a=b=ps[0]
    for p in ps[1:]:
        if p==b+1: b=p
        else:
            chunks.append(str(a) if a==b else f'{a}-{b}'); a=b=p
    chunks.append(str(a) if a==b else f'{a}-{b}')
    return ','.join(chunks)

def choose_path(q, pred_pages):
    cand=[]
    for path,n in nodes:
        ss,se=subtree_range(n)
        if all(ss<=p<=se for p in pred_pages):
            cand.append((node_score(q,path,n,pred_pages),path,n))
    if not cand:
        return []
    cand.sort(reverse=True, key=lambda x:x[0])
    path=list(cand[0][1])
    # normalize definitions in 제2장 to parent 용어의 정의 when leaf below it is selected
    if len(path)>=3 and path[0].startswith('제2장') and path[1]=='용어의 정의' and ('정의' in q or '무엇을 의미' in q or '무엇인가' in q):
        return path[:2]
    return path

# Load questions only to preserve blind generation.
rows=[]
for line in EVAL.read_text(encoding='utf-8').splitlines():
    r=json.loads(line)
    rows.append({'id':r['id'], 'question':r['question']})

preds=[]
trace=[]
for r in rows:
    ps, ranked=choose_pages(r['question'])
    path=choose_path(r['question'], ps)
    pred={
        'id':r['id'],
        'question':r['question'],
        'predicted_section_path':path,
        'predicted_pages':pages_to_str(ps),
        'evidence_pages_read':pages_to_str(ps),
        'reason':'question-only PageIndex run: ranked page content by expanded query terms, selected tight page(s), then selected best matching tree path containing those pages.'
    }
    preds.append(pred)
    trace.append({'id':r['id'],'question':r['question'],'top_pages':[(round(s,3),p) for s,p in ranked], 'chosen_pages':ps, 'chosen_path':path})

combined=OUTDIR/'predictions_001_100_blind.jsonl'
combined.write_text('\n'.join(json.dumps(p,ensure_ascii=False) for p in preds)+'\n',encoding='utf-8')
(OUTDIR/'generation_trace_001_100_blind.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for i in range(0,100,10):
    batch=preds[i:i+10]
    start=i+1; end=i+len(batch)
    (OUTDIR/f'predictions_{start:03d}_{end:03d}_blind.jsonl').write_text('\n'.join(json.dumps(p,ensure_ascii=False) for p in batch)+'\n',encoding='utf-8')
print(json.dumps({'combined':str(combined),'batches':10,'rows':len(preds)},ensure_ascii=False,indent=2))
