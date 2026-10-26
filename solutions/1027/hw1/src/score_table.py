"""과제 1 실습 ④: 4방식 점수표 (질문 유형별 정답 조항 적중률, 개정 전 인용 수, 질문당 토큰·지연)

python -m src.score_table                   # eval/results의 baseline/rag/agentic/wiki 결과(모든 회차 평균)
python -m src.score_table --methods rag agentic
"""
import argparse
import math
import statistics as st
from collections import defaultdict

from src.config import EVAL, RESULTS
from src.run_eval import citation_hit, load_jsonl, stale_citation

TYPES = [("single", "단일 사실"), ("multihop", "교차 참조"), ("synthesis", "종합"), ("trap_revision", "함정(개정)"),
         ("trap_paraphrase", "함정(표현)")]
LABEL = {"baseline": "통째 넣기", "rag": "하이브리드 RAG", "agentic": "에이전틱 검색", "wiki": "llm-wiki"}


def main(methods):
    qs = {q["id"]: q for q in load_jsonl(EVAL / "questions.jsonl")}
    print("| 방식 | " + " | ".join(t for _, t in TYPES) + " | 개정 전 판 인용(이력 포함) | 질문당 토큰 | 지연 p50(초) | 결과 파일 |")
    print("|---|" + "---|" * (len(TYPES) + 4))
    for m in methods:
        files = sorted(RESULTS.glob(f"{m}_r*.jsonl"))
        rows = [r for f in files for r in load_jsonl(f) if r["id"] in qs]
        if not rows:
            continue
        by = defaultdict(list)
        for r in rows:
            h = citation_hit(r, qs[r["id"]])
            if not math.isnan(h):
                by[r["type"]].append(h)
        cells = [f"{st.mean(by[t]):.2f}" if by[t] else "-" for t, _ in TYPES]
        stale = sum(stale_citation(r, qs[r["id"]]) for r in rows)
        tok = st.mean(r["input_tokens"] + r["output_tokens"] for r in rows)
        lat = st.median(r["latency_s"] for r in rows)
        print(f"| {LABEL.get(m, m)} | " + " | ".join(cells) + f" | {stale} | {tok:,.0f} | {lat:.1f} | {len(files)}회 |")
    print("\n값: 정답 조항(문서+조항)을 인용한 비율(0~1). 개정 전 판 인용: 정답 조항의 개정 전 판을 인용한 답 수(현행 판과 함께 이력으로 인용한 경우 포함)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", nargs="+", default=list(LABEL))
    main(ap.parse_args().methods)
