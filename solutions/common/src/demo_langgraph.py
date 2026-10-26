"""1-1 강사 시연: LangGraph 기본 개념 (State, Node, Edge, 조건부 엣지). LLM 노드 1개짜리 그래프.

python -m src.demo_langgraph "시세 전송이 20초 지연되면 통보해야 하나?"
"""
import sys
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from src.config import get_llm


class State(TypedDict, total=False):   # State: 노드들이 함께 읽고 쓰는 데이터
    question: str
    answer: str
    too_long: bool


def ask_llm(state: State) -> dict:      # Node: state를 받아 바꿀 부분만 돌려준다
    r = get_llm(max_tokens=300).invoke(f"한 문장으로 답해: {state['question']}")
    return {"answer": r.text, "too_long": len(r.text) > 120}


def shorten(state: State) -> dict:
    r = get_llm(max_tokens=100).invoke(f"다음을 60자 이내로 줄여: {state['answer']}")
    return {"answer": r.text}


g = StateGraph(State)
g.add_node("ask_llm", ask_llm)
g.add_node("shorten", shorten)
g.add_edge(START, "ask_llm")                                       # Edge: 실행 순서
g.add_conditional_edges("ask_llm", lambda s: "long" if s["too_long"] else "ok",   # 조건부 엣지
                        {"long": "shorten", "ok": END})
g.add_edge("shorten", END)
graph = g.compile()

if __name__ == "__main__":
    print(graph.get_graph().draw_mermaid())
    print(graph.invoke({"question": " ".join(sys.argv[1:]) or "RAG를 한 문장으로 설명하면?"})["answer"])
