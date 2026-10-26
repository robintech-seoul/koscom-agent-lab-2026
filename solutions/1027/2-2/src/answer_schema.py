"""인용 포함 구조화 출력 스키마. 이후 모든 그래프(에이전틱, 위키, 멀티 에이전트)가 같이 쓴다."""
from pydantic import BaseModel, Field


class Citation(BaseModel):
    doc: str = Field(description="문서명. 예: 시세정보전송규정")
    article: str = Field(description="조항 번호만. 예: 제12조 (항·호·제목은 붙이지 않는다)")
    effective_date: str = Field(description="그 조항이 실린 판의 시행일. YYYY-MM-DD")


class Answer(BaseModel):
    answer: str = Field(description="질문에 대한 답. 근거가 부족하면 '문서에 없음'")
    citations: list[Citation] = Field(description="답의 근거가 된 조항 목록. 답에 쓴 조항은 빠짐없이 넣는다. 답할 수 없으면 빈 목록")
    sufficient: bool = Field(description="주어진 근거만으로 답할 수 있으면 true")


REFUSAL = "문서에 없음: 제공된 규정에서 근거를 찾지 못해 답하지 않습니다."


def format_context(rows: list[dict]) -> str:
    """검색된 조항을 LLM에 넣을 문자열로 만든다. 시행일과 상태를 함께 보여 준다."""
    parts = []
    for r in rows:
        parts.append(f"[{r['doc']} {r['article']}({r.get('title', '')}) | 시행일 {r['effective_date']} | "
                     f"보안등급 {r['security_level']}]\n{r['text']}")
    return "\n\n".join(parts)
