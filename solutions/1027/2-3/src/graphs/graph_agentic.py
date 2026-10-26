"""에이전틱 검색 그래프 (2-3): LLM이 도구(grep, read_file, hybrid_search)를 골라 반복 호출한다.

agent ──(도구 호출 있음, 8회 미만)──▶ tools ──▶ agent
  └──(도구 호출 없음 또는 8회 도달)──▶ finalize(구조화 출력) ──▶ END
"""
import operator
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.answer_schema import REFUSAL, Answer
from src.config import get_llm
from src.tools import CURRENT_ROLE, grep, hybrid_search, read_file

MAX_ITERS = 8
ROLE_GUARD = False   # 4-2에서 True로 바꾸면 도구가 사용자 역할(role)의 권한 범위만 읽는다
TOOLS = [grep, read_file, hybrid_search]
SYSTEM = """너는 한빛시장정보(주) 사내 규정 조사 담당이다. 도구로 규정 원문을 찾아 근거를 모은다.
- hybrid_search로 관련 조항을 찾고, 다른 조항을 참조하는 문장(「문서」 제N조)이 있으면 그 조항도 찾아 읽는다.
- 고유한 번호나 코드는 grep으로 찾는 편이 빠르다. 필요하면 read_file로 원문을 연다.
- 같은 조항이 시행일이 다른 여러 판으로 있으면 시행일이 가장 늦은 판을 따른다.
- 근거가 충분하면 도구 호출을 멈추고 짧게 결론을 쓴다. 원문 폴더는 data/raw/ 이다."""
FINAL = """지금까지의 조사 내용만 근거로 질문에 답하라.
답에 쓴 조항은 모두 citations에 문서명, 조항, 시행일로 적는다. citations가 비어 있으면 안 된다.
조사 내용으로 답할 수 없으면 sufficient=false, answer='문서에 없음'."""


class State(TypedDict, total=False):
    question: str
    role: str
    messages: Annotated[list, add_messages]
    tool_log: Annotated[list[dict], operator.add]
    iterations: int
    answer: str
    citations: list[dict]
    contexts: list[str]
    refused: bool


def agent(state: State) -> dict:
    msgs = state.get("messages") or [SystemMessage(SYSTEM), HumanMessage(state["question"])]
    reply = get_llm().bind_tools(TOOLS).invoke(msgs)
    new = [] if state.get("messages") else msgs
    return {"messages": new + [reply], "iterations": state.get("iterations", 0) + 1}


_tool_node = ToolNode(TOOLS, handle_tool_errors=True)


def tools(state: State) -> dict:
    if ROLE_GUARD:
        CURRENT_ROLE.set(state.get("role") or "general")
    last = state["messages"][-1]
    out = _tool_node.invoke({"messages": state["messages"]})
    msgs = out["messages"]
    log = [{"tool": tc["name"], "args": tc["args"], "result_len": len(m.content)}
           for tc, m in zip(last.tool_calls, msgs)]
    return {"messages": msgs, "tool_log": log}


def route(state: State) -> str:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None) and state.get("iterations", 0) < MAX_ITERS:
        return "tools"
    return "finalize"


def finalize(state: State) -> dict:
    llm = get_llm().with_structured_output(Answer, method="json_schema")
    msgs = state["messages"]
    if getattr(msgs[-1], "tool_calls", None):   # 8회 도달로 끝나 실행 안 된 도구 호출은 빼고 넘긴다
        msgs = msgs[:-1]
    out: Answer = llm.invoke(msgs + [HumanMessage(FINAL)])
    contexts = [m.content for m in state["messages"] if isinstance(m, ToolMessage)]
    if not out.sufficient or not out.citations:
        return {"answer": REFUSAL, "citations": [], "contexts": contexts, "refused": True}
    return {"answer": out.answer, "citations": [c.model_dump() for c in out.citations],
            "contexts": contexts, "refused": False}


def build_graph():
    g = StateGraph(State)
    g.add_node("agent", agent)
    g.add_node("tools", tools)
    g.add_node("finalize", finalize)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route, {"tools": "tools", "finalize": "finalize"})
    g.add_edge("tools", "agent")
    g.add_edge("finalize", END)
    return g.compile()


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "시세 전송 지연을 참가사에 통보할 때 어떤 채널을 쓰나?"
    out = build_graph().invoke({"question": q, "role": "general"}, {"recursion_limit": 60})
    for t in out.get("tool_log", []):
        print("  도구:", t)
    print(out["answer"])
    for c in out.get("citations", []):
        print(" -", c)
