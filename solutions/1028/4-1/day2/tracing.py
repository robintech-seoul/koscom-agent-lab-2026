"""(선택, 4-1) Phoenix로 에이전트 호출 경로를 본다.

1) 다른 터미널에서 Phoenix 실행:  uvx arize-phoenix serve        → http://localhost:6006
   (Phoenix 서버는 MCP 라이브러리 버전이 달라 실습 가상환경과 따로 띄운다)
2) 계측을 켜고 실행:               python -m day2.tracing "A사 주식분할 ... ?"
설치(선택): uv pip install -r requirements-optional.txt
"""
import asyncio
import sys
import uuid


def enable(project: str = "koscom-agent-lab") -> None:
    from openinference.instrumentation.langchain import LangChainInstrumentor
    from phoenix.otel import register
    tp = register(project_name=project, endpoint="http://localhost:6006/v1/traces", batch=False)
    LangChainInstrumentor().instrument(tracer_provider=tp)


if __name__ == "__main__":
    enable()
    from day2.agents import build_graph
    q = " ".join(sys.argv[1:]) or "A사 주식분할에 따른 종목정보 변경 정보는 언제까지 참가사에 배포해야 하나?"
    out = asyncio.run(build_graph().ainvoke({"question": q, "role": "staff"},
                                            {"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": 80}))
    print(out["answer"])
    print("Phoenix UI에서 확인: http://localhost:6006")
