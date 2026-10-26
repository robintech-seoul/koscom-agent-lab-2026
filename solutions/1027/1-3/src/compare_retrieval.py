"""평가셋 30건에 대해 검색 방식별로 상위 k건 안에 정답 조항이 들어간 질문 수를 센다. 리랭커 적용 전후를 함께 본다.

실행: python -m src.compare_retrieval [--k 5] [--detail] [--no-rerank]
"""
import argparse
import json

from src.config import EVAL
from src.retriever import hybrid_search

MODES_ORDER = ("bm25", "bm25_kiwi", "vector", "hybrid")


def hit(results, gold) -> int:
    """2: 정답 조항을 모두 찾음, 1: 일부만 찾음, 0: 못 찾음"""
    got = {(r["doc"], r["article"]) for r in results}
    return 2 if gold <= got else (1 if gold & got else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--detail", action="store_true", help="문항별 적중 여부 출력")
    ap.add_argument("--no-rerank", action="store_true", help="리랭커 모델이 없을 때")
    a = ap.parse_args()
    qs = [json.loads(l) for l in open(EVAL / "questions.jsonl", encoding="utf-8")]
    qs = [q for q in qs if q["gold_citations"]]   # 권한 밖 문항(정답 조항 없음)은 제외
    cols = [(m, False) for m in MODES_ORDER] + ([] if a.no_rerank else [(m, True) for m in MODES_ORDER])
    table = {c: [] for c in cols}
    for q in qs:
        gold = {(c["doc"], c["article"]) for c in q["gold_citations"]}
        for m, rr in cols:
            table[(m, rr)].append(hit(hybrid_search(q["question"], k=a.k, mode=m, rerank_on=rr), gold))
    n = len(qs)
    print(f"\n상위 {a.k}건 안에 정답 조항이 들어간 질문 수 ({n}건 중, 정답 조항이 없는 권한 밖 문항 제외)")
    print("값: 하나라도 들어감 / 모두 들어감\n")
    print("| 검색 방식 | 리랭커 없음 | 리랭커 적용 |\n|---|---|---|")
    for m in MODES_ORDER:
        cells = []
        for rr in (False, True):
            hs = table.get((m, rr))
            cells.append(f"{sum(h >= 1 for h in hs)} / {sum(h == 2 for h in hs)}" if hs else "-")
        print(f"| {m} | {cells[0]} | {cells[1]} |")
    if a.detail:
        heads = [f"{m}{'+R' if rr else ''}" for m, rr in cols]
        print("\n문항별 (O: 모두, ◐: 일부, .: 못 찾음, +R: 리랭커 적용)")
        print("| id | type | " + " | ".join(heads) + " |\n|---|---|" + "---|" * len(heads))
        for i, q in enumerate(qs):
            print(f"| {q['id']} | {q['type']} | " + " | ".join("O◐."[2 - table[c][i]] for c in cols) + " |")


if __name__ == "__main__":
    main()
