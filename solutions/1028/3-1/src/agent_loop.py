"""도구를 반복 호출하는 단순 에이전트 그래프 (2일차 공용). agent ⇄ tools, 최대 max_iters회.

    graph = build_tool_agent(tools, system="...", max_iters=6)
    out = await graph.ainvoke({"question": "..."})      # MCP 도구는 비동기라 ainvoke를 쓴다
    out["answer"], out["tool_log"]
"""
import operator
import time
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.config import get_llm
from src.tools import filter_output


class LoopState(TypedDict, total=False):
    question: str
    role: str
    messages: Annotated[list, add_messages]
    tool_log: Annotated[list[dict], operator.add]
    iterations: int
    answer: str


def build_tool_agent(tools: list, system: str, max_iters: int = 6, name: str = "agent", max_tokens: int = 4000):
    llm = get_llm(max_tokens=max_tokens).bind_tools(tools)   # 출력 한도에는 모델의 생각(thinking) 토큰도 들어간다
    node = ToolNode(tools, handle_tool_errors=True)

    async def agent(state: LoopState) -> dict:
        msgs = state.get("messages") or [SystemMessage(system), HumanMessage(state["question"])]
        reply = await llm.ainvoke(msgs)
        out = {"messages": ([] if state.get("messages") else msgs) + [reply],
               "iterations": state.get("iterations", 0) + 1}
        if not getattr(reply, "tool_calls", None) or out["iterations"] >= max_iters:
            out["answer"] = reply.text if hasattr(reply, "text") else str(reply.content)
        return out

    async def run_tools(state: LoopState) -> dict:
        last = state["messages"][-1]
        t0 = time.time()
        msgs = (await node.ainvoke({"messages": state["messages"]}))["messages"]
        for m in msgs:   # MCP 도구 결과도 4-2 출력 필터를 거친다
            if isinstance(m.content, str):
                m.content = filter_output(m.content)
            elif isinstance(m.content, list):
                m.content = filter_output("\n".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in m.content))
        dt = round(time.time() - t0, 2)
        log = []
        for tc, m in zip(last.tool_calls, msgs):
            content = m.content if isinstance(m.content, str) else str(m.content)
            log.append({"agent": name, "tool": tc["name"], "args": tc["args"], "result_len": len(content),
                        "error": getattr(m, "status", "") == "error" or '"error"' in content[:200]
                        or content.startswith(("Error", "usage:")), "seconds": dt,
                        "result": content})   # 근거 추출용. 자르면 JSON을 못 읽는다(결과 파일에는 저장하지 않음)
        return {"messages": msgs, "tool_log": log}

    def route(state: LoopState) -> str:
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) and state.get("iterations", 0) < max_iters else "end"

    g = StateGraph(LoopState)
    g.add_node("agent", agent)
    g.add_node("tools", run_tools)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route, {"tools": "tools", "end": END})
    g.add_edge("tools", "agent")
    return g.compile()
