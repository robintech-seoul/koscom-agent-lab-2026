"""4-3 실습 ②: 개정 반영 후 RAG와 위키를 같은 문항으로 비교한다.

전제: python -m day2.update_index 실행 완료(RAG 쪽), 위키는 wiki/를 갱신했거나 data/wiki_updated 사용.
python -m day2.compare_update [--wiki data/wiki_updated]
"""
import argparse
import json
import os

from src.config import EVAL
from src.run_eval import cite_key, load_jsonl, run_one


def judge(row, q) -> str:
    """정답(현행 조항·시행일 일치) / 개정 전 인용 / 누락"""
    gold = {(*cite_key(c), c["effective"]) for c in q["gold_citations"]}
    got = {(*cite_key(c), c.get("effective_date")) for c in row.get("citations", [])}
    if gold <= got:
        old = {(d, a) for d, a, _ in gold}
        return "정답(이력 함께 인용)" if any((d, a) in old and (d, a, e) not in gold for d, a, e in got) else "정답"
    if {(d, a) for d, a, _ in gold} & {(d, a) for d, a, _ in got}:
        return "개정 전 인용"
    return "누락"


def main(wiki: str):
    os.environ["WIKI_DIR"] = wiki
    from day2.update_index import current_filter
    from src import retriever
    from src.graphs import graph_rag, graph_wiki
    retriever.DEFAULT_FILTERS.update(current_filter("2026-10-27"))
    qs = load_jsonl(EVAL / "sets" / "updates.jsonl") + [q for q in load_jsonl(EVAL / "questions.jsonl")
                                                         if q["type"] == "trap_revision"]
    print("| id | 질문 | RAG | 위키 |\n|---|---|---|---|")
    rows = {"rag": [], "wiki": []}
    for q in qs:
        r1 = run_one(graph_rag.build_graph(), q, "rag_updated")
        r2 = run_one(graph_wiki.build_graph(), q, "wiki_updated")
        rows["rag"].append(r1)
        rows["wiki"].append(r2)
        print(f"| {q['id']} | {q['question'][:30]} | {judge(r1, q)} | {judge(r2, q)} |")
    for k, rs in rows.items():
        with open(EVAL / "results" / f"{k}_updated_r1.jsonl", "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rs)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--wiki", default="data/wiki_updated")
    main(ap.parse_args().wiki)
