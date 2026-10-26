"""3-3: 결합 질문 결과에서 출처 누락 수와 중복 검색 수를 센다. 3-2(순차, 중복 제거 없음)와 3-3(evidence 공유, Send 병렬, 중복 제거)을 비교한다.

python -m day2.compare_fusion eval/results/multi_r1.jsonl eval/results/fusion_r1.jsonl

- 출처 누락: 정답에 필요한 규정 조항(gold_citations)과 공시 접수번호(gold_rcept) 중 답의 인용에 없는 것
- 중복 검색: 한 질문 안에서 같은 도구를 같은 인자로 다시 부른 횟수 (담당 에이전트가 달라도 센다)
- 중복 근거: writer에 들어간 근거(contexts) 중 같은 내용이 두 번 이상 들어간 수
"""
import json
import sys

from src.config import EVAL, root_path


def load(p):
    return [json.loads(l) for l in open(root_path(p), encoding="utf-8") if l.strip()]


def main(paths):
    gold = {q["id"]: q for q in load(EVAL / "sets" / "combined.jsonl")}
    print("| 결과 파일 | 출처 누락 (질문 수) | 출처 누락 (항목 수) | 중복 검색 | 중복 근거 | 질문당 토큰 | 지연 중앙값 |")
    print("|---|---|---|---|---|---|---|")
    for p in paths:
        rows = load(p)
        miss_q = miss_items = dup_calls = dup_ctx = 0
        for r in rows:
            g = gold.get(r["id"], {})
            got_reg = {(c["doc"], c["article"]) for c in r.get("citations", [])}
            got_dart = {c["article"] for c in r.get("citations", []) if c["doc"].upper().startswith("DART")}
            need = [(c["doc"], c["article"]) for c in g.get("gold_citations", [])]
            m = sum(1 for n in need if n not in got_reg) + sum(1 for x in g.get("gold_rcept", []) if x not in got_dart)
            miss_items += m
            miss_q += m > 0
            seen = set()
            for t in r.get("tool_calls", []):
                k = (t.get("tool"), json.dumps(t.get("args", {}), ensure_ascii=False, sort_keys=True))
                dup_calls += k in seen
                seen.add(k)
            ctx = r.get("contexts", [])
            dup_ctx += len(ctx) - len(set(ctx))
        lat = sorted(r["latency_s"] for r in rows)[len(rows) // 2]
        tok = sum(r["input_tokens"] + r["output_tokens"] for r in rows) / len(rows)
        print(f"| {p} | {miss_q} / {len(rows)} | {miss_items} | {dup_calls} | {dup_ctx} | {tok:,.0f} | {lat}초 |")


if __name__ == "__main__":
    main(sys.argv[1:])
