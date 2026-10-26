"""RAGAS 채점 (2-1): faithfulness, context_recall

- judge LLM은 그래프와 같은 모델(CLAUDE.md 고정)을 BizRouter의 OpenAI 호환 주소로 부른다.
- 기준선(Claude Code 결과)은 검색 문맥이 없으므로 faithfulness 문맥을 data/regs_all.md 전체로 하고,
  context_recall은 1.0으로 기록한다(전체 문서가 문맥이므로 정의상 1.0).
"""
import asyncio
import os

from src.config import DATA, MODEL

CONCURRENCY = 4


def _judge():
    """RAGAS judge LLM.
    RAGAS 0.4.3의 llm_factory는 json_object 모드로 요청하는데, BizRouter의 Claude는 json_schema만 받는다.
    그래서 instructor 클라이언트를 MD_JSON 모드(프롬프트로 JSON을 요청하고 응답에서 꺼냄)로 직접 만들어 넘긴다."""
    import instructor
    from openai import AsyncOpenAI
    from ragas.llms.base import InstructorLLM, InstructorModelArgs
    raw = AsyncOpenAI(base_url="https://api.bizrouter.ai/v1", api_key=os.environ["BIZROUTER_API_KEY"])
    client = instructor.from_openai(raw, mode=instructor.Mode.MD_JSON)
    return InstructorLLM(client=client, model=MODEL, provider="openai",
                         model_args=InstructorModelArgs(temperature=0.0, max_tokens=8000))


async def _score_all(rows, qs, baseline):
    from ragas.metrics.collections import ContextRecall, Faithfulness
    llm = _judge()
    faith, recall = Faithfulness(llm=llm), ContextRecall(llm=llm)
    full = [(DATA / "regs_all.md").read_text(encoding="utf-8")] if baseline else None
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(r):
        q = qs.get(r["id"], {})
        ctx = full or r.get("contexts") or [""]
        out = {}
        async with sem:
            if r.get("refused") or not r.get("answer"):
                return r["id"], {"faithfulness": None, "context_recall": None}
            try:
                out["faithfulness"] = round(float((await faith.ascore(
                    user_input=r["question"], response=r["answer"], retrieved_contexts=ctx)).value), 3)
            except Exception as e:  # noqa: BLE001
                out["faithfulness"], out["ragas_error"] = None, f"faith: {e}"[:200]
            if baseline:
                out["context_recall"] = 1.0
            elif q.get("gold_citations"):
                try:
                    out["context_recall"] = round(float((await recall.ascore(
                        user_input=r["question"], retrieved_contexts=ctx, reference=q["gold_answer"])).value), 3)
                except Exception as e:  # noqa: BLE001
                    out["context_recall"], out["ragas_error"] = None, f"recall: {e}"[:200]
        return r["id"], out

    return dict(await asyncio.gather(*(one(r) for r in rows)))


def ragas_scores(rows: list[dict], qs: dict, baseline: bool = False) -> dict:
    return asyncio.run(_score_all(rows, qs, baseline))
