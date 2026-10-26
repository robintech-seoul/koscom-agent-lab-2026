"""구조별 비용·지연·점수 표 (4-1): eval/results/의 모든 결과 jsonl을 읽는다.

python -m src.cost_table [--daily 1000]     # 하루 질의 수를 넣으면 일 비용도 계산
"""
import argparse
import json
import statistics as st
from collections import defaultdict

from src.config import RESULTS
from src.run_eval import citation_hit, load_jsonl
from src.config import EVAL

LABEL = {"baseline": "기준선(통째 넣기)", "rag": "RAG", "agentic": "에이전틱", "wiki": "위키",
         "single": "단일 에이전트", "multi": "멀티 에이전트"}


def main(daily: int):
    qs = {}
    for f in [EVAL / "questions.jsonl", *sorted((EVAL / "sets").glob("*.jsonl"))]:
        for q in load_jsonl(f):
            qs[q["id"]] = q
    groups = defaultdict(list)
    for p in sorted(RESULTS.glob("*_r*.jsonl")):
        method = p.stem.rsplit("_r", 1)[0]
        if method in LABEL:
            groups[method] += load_jsonl(p)
    print(f"| 구조 | 결과 수 | 질문당 입력 토큰 | 질문당 출력 토큰 | 질문당 비용(USD) | 일 {daily}건 비용(USD) | p50 지연(초) | p95 지연(초) | 정답 조항 적중 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for m in LABEL:
        rows = groups.get(m)
        if not rows:
            continue
        lat = sorted(r["latency_s"] for r in rows)
        hits = [h for r in rows if (h := citation_hit(r, qs.get(r["id"], {}))) == h]   # NaN 제외
        cost = st.mean(r["cost_usd"] for r in rows)
        print(f"| {LABEL[m]} | {len(rows)} | {st.mean(r['input_tokens'] for r in rows):,.0f} | "
              f"{st.mean(r['output_tokens'] for r in rows):,.0f} | {cost:.4f} | {cost * daily:,.1f} | "
              f"{st.median(lat):.1f} | {lat[min(len(lat) - 1, int(0.95 * len(lat)))]:.1f} | "
              f"{(sum(hits) / len(hits)) if hits else float('nan'):.2f} |")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily", type=int, default=1000)
    main(ap.parse_args().daily)
