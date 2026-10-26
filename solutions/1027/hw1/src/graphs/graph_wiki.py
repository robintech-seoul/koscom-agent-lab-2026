"""위키 에이전트 (과제 1): 위키를 지도로 쓰고, 근거는 원문 조항으로 확인한다.

도구: read_index(), read_page(name), read_source(doc, article)
최종 citations는 read_source로 실제 확인한 조항만 남긴다.
"""
import operator
import os
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.answer_schema import REFUSAL, Answer
from src.config import LEVEL_DIR, ROLE_LEVELS, ROOT, get_llm
from src.tools import CURRENT_ROLE, read_source

MAX_ITERS = 8
ROLE_GUARD = False   # 4-2: True면 역할별 위키 디렉터리만 읽는다


def wiki_dir():
    """환경 변수 WIKI_DIR > 학생이 만든 wiki/(index.md가 있을 때) > 미리 만든 위키 data/wiki 순으로 쓴다."""
    if os.environ.get("WIKI_DIR"):
        return ROOT / os.environ["WIKI_DIR"]
    return ROOT / "wiki" if (ROOT / "wiki" / "index.md").exists() else ROOT / "data" / "wiki"


def _allowed_levels():
    return ROLE_LEVELS.get(CURRENT_ROLE.get(), ["일반"]) if ROLE_GUARD else list(LEVEL_DIR)


@tool
def read_index() -> str:
    """위키 목차(index.md)를 읽는다. 어떤 페이지가 어떤 주제와 문서를 다루는지 나온다."""
    lines = (wiki_dir() / "index.md").read_text(encoding="utf-8").splitlines()
    lv = _allowed_levels()
    return "\n".join(l for l in lines if not l.startswith("| [[") or l.split("|")[2].strip() in lv)


@tool
def read_page(name: str) -> str:
    """위키 페이지 하나를 읽는다. name 예: 시세-전송-지연"""
    name = name.strip("[] ").removesuffix(".md")
    for lv in _allowed_levels():
        p = wiki_dir() / "pages" / LEVEL_DIR[lv] / f"{name}.md"
        if p.exists():
            return p.read_text(encoding="utf-8")
    return f"페이지 없음 또는 접근 권한 없음: {name}"


TOOLS = [read_index, read_page, read_source]
SYSTEM = """너는 사내 규정 위키를 지도로 써서 답을 찾는다.
1) read_index로 관련 페이지를 고르고 2) read_page로 읽은 뒤
3) 답에 쓸 내용의 근거 링크 [문서 §조항, 시행일]를 read_source(doc, article)로 원문에서 반드시 확인한다.
위키 문장만 보고 답하지 않는다. 원문과 위키가 다르면 원문을 따른다."""
FINAL = """read_source로 확인한 원문 조항만 근거로 답하라. citations에는 read_source로 확인한 조항만 넣는다.
답할 수 없으면 sufficient=false, answer='문서에 없음'."""


class State(TypedDict, total=False):
    question: str
    role: str
    messages: Annotated[list, add_messages]
    tool_log: Annotated[list[dict], operator.add]
    verified: Annotated[list[str], operator.add]
    iterations: int
    answer: str
    citations: list[dict]
    contexts: list[str]
    refused: bool


def agent(state: State) -> dict:
    msgs = state.get("messages") or [SystemMessage(SYSTEM), HumanMessage(state["question"])]
    reply = get_llm().bind_tools(TOOLS).invoke(msgs)
    return {"messages": ([] if state.get("messages") else msgs) + [reply],
            "iterations": state.get("iterations", 0) + 1}


_tool_node = ToolNode(TOOLS, handle_tool_errors=True)


def tools(state: State) -> dict:
    if ROLE_GUARD:
        CURRENT_ROLE.set(state.get("role") or "general")
    last = state["messages"][-1]
    msgs = _tool_node.invoke({"messages": state["messages"]})["messages"]
    log, verified = [], []
    for tc, m in zip(last.tool_calls, msgs):
        log.append({"tool": tc["name"], "args": tc["args"], "result_len": len(m.content)})
        if tc["name"] == "read_source" and not m.content.startswith(("조항 없음", "접근 권한 없음")):
            verified.append(f"{tc['args'].get('doc', '').replace(' ', '')}|{tc['args'].get('article', '')}")
    return {"messages": msgs, "tool_log": log, "verified": verified}


def route(state: State) -> str:
    last = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) and state.get("iterations", 0) < MAX_ITERS else "finalize"


def finalize(state: State) -> dict:
    msgs = state["messages"][:-1] if getattr(state["messages"][-1], "tool_calls", None) else state["messages"]
    out: Answer = get_llm().with_structured_output(Answer, method="json_schema").invoke(msgs + [HumanMessage(FINAL)])
    ok = set(state.get("verified", []))
    cites = [c.model_dump() for c in out.citations if f"{c.doc.replace(' ', '')}|{c.article}" in ok]
    contexts = [m.content for m in state["messages"] if isinstance(m, ToolMessage) and m.content.startswith("[")]
    if not out.sufficient or not cites:
        return {"answer": REFUSAL, "citations": [], "contexts": contexts, "refused": True}
    return {"answer": out.answer, "citations": cites, "contexts": contexts, "refused": False}


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
    q = " ".join(sys.argv[1:]) or "1등급 장애가 발생했을 때 해야 할 일을 시간 순서로 정리하라."
    out = build_graph().invoke({"question": q, "role": "staff"}, {"recursion_limit": 60})
    for t in out.get("tool_log", []):
        print("  도구:", t)
    print(out["answer"])
    for c in out.get("citations", []):
        print(" -", c)
