"""평가 러너: 그래프 모듈을 평가셋 전체에 돌려 결과 jsonl을 만들고, 채점한다.

실행
    python -m src.run_eval --graph src.graphs.graph_rag --name rag --run 1
    python -m src.run_eval --graph src.graphs.graph_rag --name rag_oos --set eval/sets/out_of_scope.jsonl
    python -m src.run_eval --results eval/results/rag_r1.jsonl --score       # 채점만 (2-1)
    python -m src.run_eval --results eval/results/baseline_r1.jsonl --score --baseline
"""
import argparse
import asyncio
import csv
import importlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from langchain_core.callbacks import get_usage_metadata_callback

from src.config import EVAL, MODEL, RESULTS, ROOT, root_path, usage_from_callback

QUESTIONS = EVAL / "questions.jsonl"


def load_jsonl(path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def save_jsonl(path, rows) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


# ---------- 실행 ----------
def run_one(graph, q: dict, method: str, is_async: bool = False) -> dict:
    t0 = time.time()
    err = None
    inp = {"question": q["question"], "role": q.get("role", "general")}
    cfg = {"configurable": {"thread_id": f"{method}-{q['id']}-{t0}"}, "recursion_limit": 80}
    with get_usage_metadata_callback() as cb:
        try:
            # 2일차 그래프(MCP 도구 사용)는 비동기라 ainvoke로 실행한다
            out = asyncio.run(graph.ainvoke(inp, cfg)) if is_async else graph.invoke(inp, cfg)
        except Exception as e:  # noqa: BLE001 — 한 문항 실패가 전체를 멈추지 않게
            out, err = {}, f"{type(e).__name__}: {e}"
    usage = usage_from_callback(cb.usage_metadata)
    return {
        "id": q["id"], "type": q["type"], "question": q["question"],
        "answer": out.get("answer", ""), "citations": out.get("citations", []),
        "contexts": out.get("contexts", []), "refused": bool(out.get("refused", False)),
        **usage, "latency_s": round(time.time() - t0, 2),
        "tool_calls": out.get("tool_log", []), "method": method, "model": MODEL,
        **({"error": err} if err else {}),
    }


def run_graph(module: str, name: str, run: int, qset: Path, limit: int | None, workers: int) -> Path:
    mod = importlib.import_module(module)
    graph, is_async = mod.build_graph(), getattr(mod, "IS_ASYNC", False)
    qs = load_jsonl(qset)[:limit] if limit else load_jsonl(qset)
    out_path = RESULTS / f"{name}_r{run}.jsonl"
    with ThreadPoolExecutor(max_workers=workers) as ex:
        rows = list(ex.map(lambda q: run_one(graph, q, name, is_async), qs))
    save_jsonl(out_path, rows)
    n_err = sum(1 for r in rows if r.get("error"))
    print(f"{len(rows)}건 → {out_path.relative_to(ROOT)} (오류 {n_err}건)")
    return out_path


# ---------- 채점 (함수만 분리: 2-1에서 RAGAS를 여기에 붙인다) ----------
ART_RE = re.compile(r"제\d+조(?:의\d+)?|부칙")


def norm_article(a: str) -> str:
    """'제4조(1등급)', '제12조 제1항' → '제4조', '제12조'"""
    m = ART_RE.search(a or "")
    return m.group(0) if m else (a or "")


def cite_key(c: dict) -> tuple:
    return (c.get("doc", "").replace(" ", "").strip("「」"), norm_article(c.get("article", "")))


def citation_hit(row: dict, q: dict) -> float:
    """정답 조항(문서+조항)을 몇 개 인용했나. 0~1"""
    gold = {cite_key(c) for c in q.get("gold_citations", [])}
    if not gold:
        return float("nan")
    got = {cite_key(c) for c in row.get("citations", [])}
    return len(gold & got) / len(gold)


def stale_citation(row: dict, q: dict) -> bool:
    """정답과 같은 조항을 인용했지만 시행일이 다르면(개정 전 판) True"""
    gold = {cite_key(c): c.get("effective") for c in q.get("gold_citations", [])}
    for c in row.get("citations", []):
        k = cite_key(c)
        if k in gold and c.get("effective_date") and c["effective_date"] != gold[k]:
            return True
    return False


def leaked(row: dict, q: dict) -> bool:
    """권한 밖 문서를 인용했거나, 금지 문자열이 답에 나왔는가"""
    bad_docs = set(q.get("forbidden_docs", []))
    if any(c.get("doc") in bad_docs for c in row.get("citations", [])):
        return True
    return any(s in (row.get("answer") or "") for s in q.get("must_not_contain", []))


def score_rows(rows: list[dict], qs: dict, baseline: bool = False, ragas: bool = False) -> list[dict]:
    scored = []
    for r in rows:
        q = qs.get(r["id"], {})
        s = {"id": r["id"], "type": r.get("type"), "citation_hit": citation_hit(r, q),
             "stale_citation": stale_citation(r, q), "leaked": leaked(r, q), "refused": r.get("refused", False),
             "no_citation": (not r.get("citations")) and not r.get("refused", False)}
        scored.append(s)
    if ragas:
        from src.ragas_score import ragas_scores
        rs = ragas_scores(rows, qs, baseline=baseline)
        for s in scored:
            s.update(rs.get(s["id"], {}))
    return scored


def summarize(name: str, rows: list[dict], scored: list[dict]) -> dict:
    import math
    import statistics as st

    def mean(xs):
        xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
        return round(sum(xs) / len(xs), 3) if xs else None

    lat = sorted(r.get("latency_s", 0) for r in rows)
    return {
        "name": name, "n": len(rows),
        "citation_hit": mean([s["citation_hit"] for s in scored]),
        "faithfulness": mean([s.get("faithfulness") for s in scored]),
        "context_recall": mean([s.get("context_recall") for s in scored]),
        "stale": sum(s["stale_citation"] for s in scored), "leaked": sum(s["leaked"] for s in scored),
        "no_citation": sum(s["no_citation"] for s in scored), "refused": sum(s["refused"] for s in scored),
        "in_tok": mean([r.get("input_tokens", 0) for r in rows]), "out_tok": mean([r.get("output_tokens", 0) for r in rows]),
        "cost_usd": mean([r.get("cost_usd", 0) for r in rows]),
        "p50_s": round(st.median(lat), 2) if lat else None,
        "p95_s": round(lat[min(len(lat) - 1, int(0.95 * len(lat)))], 2) if lat else None,
    }


def append_scores(name: str, scored: list[dict], summary: dict) -> None:
    path = RESULTS / "scores.csv"
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "result", "id", "metric", "value"])
        now = datetime.now().isoformat(timespec="seconds")
        for s in scored:
            for m in ("citation_hit", "faithfulness", "context_recall"):
                if s.get(m) is not None:
                    w.writerow([now, name, s["id"], m, s[m]])
        for m, v in summary.items():
            if m not in ("name",):
                w.writerow([now, name, "_mean", m, v])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", help="그래프 모듈 경로 (예: src.graphs.graph_rag)")
    ap.add_argument("--results", help="이미 있는 결과 jsonl 경로")
    ap.add_argument("--name", default=None)
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--set", default=str(QUESTIONS), help="질문 파일 (기본: eval/questions.jsonl)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--score", action="store_true", help="RAGAS 채점까지 (2-1)")
    ap.add_argument("--baseline", action="store_true", help="기준선 결과: 문맥 = data/regs_all.md 전체")
    a = ap.parse_args()

    qset = root_path(a.set)
    if a.graph:
        name = a.name or a.graph.rsplit(".", 1)[-1].replace("graph_", "")
        path = run_graph(a.graph, name, a.run, qset, a.limit, a.workers)
    elif a.results:
        path = root_path(a.results)
    else:
        ap.error("--graph 또는 --results 중 하나가 필요하다")
    rows = load_jsonl(path)
    qs = {q["id"]: q for q in load_jsonl(qset)}
    scored = score_rows(rows, qs, baseline=a.baseline, ragas=a.score)
    summary = summarize(path.stem, rows, scored)
    append_scores(path.stem, scored, summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
