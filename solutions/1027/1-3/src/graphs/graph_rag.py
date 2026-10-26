"""하이브리드 RAG 그래프 (1-3 단계): retrieve → generate

2-2에서 generate를 구조화 출력(answer_schema)으로 바꾸고 근거가 부족하면 refuse로 보내는 분기를 붙인다.
"""
import re
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from src.config import get_llm
from src.retriever import hybrid_search

K = 6
SYSTEM = """너는 한빛시장정보(주) 사내 규정 안내 비서다. 아래 [근거] 조항만 사용해 답한다.
답에는 근거 조항을 「문서명」 제N조(시행일) 형식으로 적는다."""


class State(TypedDict, total=False):
    question: str
    role: str
    docs: list[dict]
    contexts: list[str]
    answer: str
    citations: list[dict]


# 답 본문의 「문서명」 제N조(시행일 YYYY-MM-DD)를 찾아 인용 목록으로 기록한다 (2-2에서는 구조화 출력으로 바꾼다)
CITE_RE = re.compile(r"「([^」]+)」\s*(제\d+조(?:의\d+)?)(?:[^\n「]*?(\d{4}-\d{2}-\d{2}))?")


def extract_citations(answer: str) -> list[dict]:
    out, seen = [], set()
    for doc, art, date in CITE_RE.findall(answer):
        if (doc, art, date) not in seen:
            seen.add((doc, art, date))
            out.append({"doc": doc.replace(" ", ""), "article": art, "effective_date": date})
    return out


def retrieve(state: State) -> dict:
    docs = hybrid_search(state["question"], k=K)
    ctx = [f"[{d['doc']} {d['article']}({d['title']}) | 시행일 {d['effective_date']}]\n{d['text']}" for d in docs]
    return {"docs": docs, "contexts": ctx}


def generate(state: State) -> dict:
    msg = "[근거]\n" + "\n\n".join(state["contexts"]) + f"\n\n[질문]\n{state['question']}"
    answer = get_llm().invoke([("system", SYSTEM), ("user", msg)]).text
    return {"answer": answer, "citations": extract_citations(answer)}


def build_graph():
    g = StateGraph(State)
    g.add_node("retrieve", retrieve)
    g.add_node("generate", generate)
    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "generate")
    g.add_edge("generate", END)
    return g.compile()


if __name__ == "__main__":
    import sys
    print(build_graph().invoke({"question": " ".join(sys.argv[1:]) or "시세 전송 지연 시 참가사 통보 기준은?"})["answer"])
