"""사람 승인 흐름 시연 (4-2): 비밀 등급 문서를 인용하는 답이면 interrupt()로 멈추고, 승인/거부 후 재개한다.

python -m day2.approval_demo            # 터미널에서 yes/no 입력
python -m day2.approval_demo --answer no
"""
import argparse
import asyncio
import uuid

from langgraph.types import Command

from day2.agents import build_graph

Q = "관리자 계정 발급은 누가 승인하나?"


async def main(answer: str | None):
    graph = build_graph()                      # InMemorySaver checkpointer 포함
    cfg = {"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": 80}
    out = await graph.ainvoke({"question": Q, "role": "admin"}, cfg)
    if "__interrupt__" in out:
        info = out["__interrupt__"][0].value
        print("⏸  승인 대기:", info["message"])
        for c in info["citations"]:
            print("   인용:", c)
        decision = answer or input("승인? (yes/no) > ").strip()
        out = await graph.ainvoke(Command(resume=decision), cfg)     # 같은 thread_id로 재개
    print("답:", out.get("answer"))
    print("승인 여부:", out.get("approved"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--answer", choices=["yes", "no"], default=None)
    asyncio.run(main(ap.parse_args().answer))
