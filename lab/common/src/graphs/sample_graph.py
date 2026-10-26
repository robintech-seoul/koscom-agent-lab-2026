"""1-2 평가 러너 동작 확인용 샘플 그래프. 검색 없이 질문만 LLM에 보내 한 문장으로 답한다.

python -m src.run_eval --graph src.graphs.sample_graph --name sample --limit 3
점수는 의미가 없다. 결과 파일에 답변, 토큰, 지연이 기록되는지만 본다.
"""
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from src.config import get_llm


class State(TypedDict, total=False):
    question: str
    role: str
    answer: str
    citations: list
    contexts: list


def answer(state: State) -> dict:
    r = get_llm(max_tokens=150).invoke(f"한 문장으로 답해: {state['question']}")
    return {"answer": r.text, "citations": [], "contexts": []}


def build_graph():
    g = StateGraph(State)
    g.add_node("answer", answer)
    g.add_edge(START, "answer")
    g.add_edge("answer", END)
    return g.compile()
