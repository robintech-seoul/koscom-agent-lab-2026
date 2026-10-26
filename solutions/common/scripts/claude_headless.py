"""Claude Code 헤드리스 실행 공용 함수 (Windows·Mac 공통). 결과를 CLAUDE.md 결과 형식 한 줄로 바꾼다.

- Claude Code는 각자 로그인한 Claude 구독 계정으로만 실행한다(모델 claude-haiku-5-5). API 키로 실행하지 않는다.
- 프롬프트는 표준 입력으로 넘긴다(Windows의 claude.cmd는 여러 줄 인자를 망가뜨린다).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # common/
from src.config import PRICE, ROOT  # noqa: E402  (.env도 여기서 읽힌다)

CITE_RE = re.compile(r"「?([가-힣A-Za-z]+(?:규정|절차|기준|지침|매뉴얼|계획))」?\s*(제\d+조)"
                     r"(?:[^\n(]*?\(?(?:시행일?\s*)?(\d{4}-\d{2}-\d{2}))?")


def claude_exe() -> str:
    exe = shutil.which("claude")
    if not exe:
        raise FileNotFoundError("claude 명령을 찾을 수 없다. Claude Code를 설치한다")
    return exe


CLAUDE_MODEL = "claude-haiku-5-5"   # 그래프와 같은 Haiku 5.5. 구독 계정은 Anthropic 모델 ID를 쓴다


def claude_env() -> dict:
    """API 키 환경 변수를 지워, 로그인한 구독 계정으로 실행되게 한다."""
    return {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL")}


def run_claude(prompt: str, allowed_tools: list[str], timeout: int = 600) -> tuple[dict, float]:
    """claude -p 를 실행하고 (JSON 출력, 걸린 초)를 돌려준다."""
    cmd = [claude_exe(), "-p", "--model", CLAUDE_MODEL, "--output-format", "json",
           "--allowedTools", *allowed_tools, "--setting-sources", "project"]
    t0 = time.time()
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                       env=claude_env(), cwd=ROOT, timeout=timeout)
    try:
        d = json.loads(r.stdout[r.stdout.index("{"):])
    except ValueError:
        d = {"is_error": True, "result": (r.stdout or r.stderr)[:500]}
    return d, time.time() - t0


def to_result(q: dict, d: dict, latency: float, method: str) -> dict:
    """claude JSON 출력 → eval/results 한 줄 (답변 본문에서 「문서」 제N조(시행일)를 찾아 인용으로 기록)"""
    u = d.get("usage", {})
    inp, out = u.get("input_tokens", 0), u.get("output_tokens", 0)
    cr, cw = u.get("cache_read_input_tokens", 0), u.get("cache_creation_input_tokens", 0)
    answer = d.get("result", "")
    cites, seen = [], set()
    for doc, art, date in CITE_RE.findall(answer):
        if (doc, art) not in seen:
            seen.add((doc, art))
            cites.append({"doc": doc, "article": art, "effective_date": date or ""})
    cost = d.get("total_cost_usd") or (inp * PRICE["input"] + out * PRICE["output"]
                                       + cr * PRICE["cache_read"] + cw * PRICE["cache_write"]) / 1e6
    row = {"id": q["id"], "type": q["type"], "question": q["question"], "answer": answer, "citations": cites,
           "contexts": [], "refused": answer.strip().startswith("문서에 없"),
           "input_tokens": inp + cr + cw, "output_tokens": out, "cost_usd": round(cost, 6),
           "latency_s": round(latency, 2), "tool_calls": [], "num_turns": d.get("num_turns"),
           "method": method, "model": CLAUDE_MODEL}
    if d.get("is_error"):
        row["error"] = str(d.get("result", ""))[:300]
    return row


def run_batch(prompt_tpl: str, tools: list[str], method: str, run: int, workers: int, qfile: str) -> Path:
    from concurrent.futures import ThreadPoolExecutor
    qs = [json.loads(l) for l in open(ROOT / qfile, encoding="utf-8") if l.strip()]
    print(f"{method} {run}회차: {len(qs)}건, 동시 {workers}개")

    def one(q):
        d, sec = run_claude(prompt_tpl.format(question=q["question"]), tools)
        print(f"  {q['id']} 완료 ({sec:.0f}초)", flush=True)
        return to_result(q, d, sec, method)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        rows = list(ex.map(one, qs))
    out = ROOT / "eval" / "results" / f"{method}_r{run}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(rows)}건 → {out.relative_to(ROOT)} (오류 {sum('error' in r for r in rows)}건)")
    return out
