"""하이브리드 RAG 그래프: retrieve → generate → (근거 부족이면) refuse

1-3에서 retrieve → generate 두 노드로 만들고,
2-2에서 generate를 구조화 출력(answer_schema)으로 바꾸고 refuse 분기를 붙였다.
"""
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from src.answer_schema import REFUSAL, Answer, format_context
from src.config import get_llm
from src.retriever import hybrid_search

K = 6
SYSTEM = """너는 한빛시장정보(주) 사내 규정 안내 비서다.
아래 [근거] 조항만 사용해 답한다. 근거에 없는 내용은 추측하지 않는다.
- 같은 문서의 같은 조항이 시행일이 다른 여러 판으로 나오면 시행일이 가장 늦은 판을 따른다.
- 답에 쓴 조항은 하나도 빠짐없이 citations에 문서명, 조항, 시행일로 적는다. citations가 비어 있으면 안 된다.
- 근거로 답할 수 없으면 sufficient=false로 하고 answer에 '문서에 없음'이라고 쓴다."""


class State(TypedDict, total=False):
    question: str
    role: str
    filters: dict
    docs: list[dict]
    contexts: list[str]
    answer: str
    citations: list[dict]
    sufficient: bool
    refused: bool


def retrieve(state: State) -> dict:
    docs = hybrid_search(state["question"], k=K, filters=state.get("filters"))
    return {"docs": docs, "contexts": [format_context([d]) for d in docs]}


def generate(state: State) -> dict:
    llm = get_llm().with_structured_output(Answer, method="json_schema")
    msg = f"[근거]\n{format_context(state['docs'])}\n\n[질문]\n{state['question']}"
    out: Answer = llm.invoke([("system", SYSTEM), ("user", msg)])
    return {"answer": out.answer, "citations": [c.model_dump() for c in out.citations],
            "sufficient": out.sufficient, "refused": False}


def route(state: State) -> str:
    return "ok" if state.get("sufficient") and state.get("citations") else "refuse"


def refuse(state: State) -> dict:
    return {"answer": REFUSAL, "citations": [], "refused": True}


def build_graph():
    g = StateGraph(State)
    g.add_node("retrieve", retrieve)
    g.add_node("generate", generate)
    g.add_node("refuse", refuse)
    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_conditional_edges("generate", route, {"ok": END, "refuse": "refuse"})
    g.add_edge("refuse", END)
    return g.compile()


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "시세 전송 지연 시 참가사 통보 기준은?"
    out = build_graph().invoke({"question": q, "role": "general"})
    print(out["answer"])
    for c in out.get("citations", []):
        print(" -", c)
