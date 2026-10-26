"""결합 질문 결과 비교 (3-2, 3-3): 정확도(정답 조항·접수번호 포함), 출처 누락, 중복 검색 수, 지연, 토큰

python -m day2.compare_runs eval/results/single_r1.jsonl eval/results/multi_r1.jsonl
"""
import json
import sys
from collections import Counter

from src.config import EVAL, root_path
from src.run_eval import cite_key


def check(row, q) -> dict:
    ans = row.get("answer", "")
    cites = row.get("citations", [])
    reg_ok = all(any(cite_key(c) == cite_key(g) for c in cites) for g in q.get("gold_citations", []))
    dart_ok = all(r in ans or any(c.get("article") == r for c in cites) for r in q.get("gold_rcept", []))
    calls = Counter(json.dumps([t.get("tool"), t.get("args")], ensure_ascii=False, sort_keys=True)
                    for t in row.get("tool_calls", []))
    return {"correct": reg_ok and dart_ok, "missing_source": not (reg_ok and dart_ok) and not row.get("refused"),
            "dup_calls": sum(n - 1 for n in calls.values() if n > 1)}


def main(paths):
    qs = {}
    for f in ("combined.jsonl", "dart.jsonl"):
        for l in open(EVAL / "sets" / f, encoding="utf-8"):
            q = json.loads(l)
            qs[q["id"]] = q
    print("| 결과 | 정답 근거 포함 | 출처 누락 | 중복 검색 | 평균 지연(초) | 질문당 입력 토큰 | 질문당 비용(USD) |")
    print("|---|---|---|---|---|---|---|")
    for p in paths:
        rows = [json.loads(l) for l in open(root_path(p), encoding="utf-8")]
        cs = [check(r, qs[r["id"]]) for r in rows]
        n = len(rows)
        print(f"| {p.split('/')[-1]} | {sum(c['correct'] for c in cs)}/{n} | {sum(c['missing_source'] for c in cs)} | "
              f"{sum(c['dup_calls'] for c in cs)} | {sum(r['latency_s'] for r in rows) / n:.1f} | "
              f"{sum(r['input_tokens'] for r in rows) / n:.0f} | {sum(r['cost_usd'] for r in rows) / n:.3f} |")


if __name__ == "__main__":
    main(sys.argv[1:])
