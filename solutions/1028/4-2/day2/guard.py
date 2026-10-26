"""권한, 보안, 사람 승인 (4-2)

- 역할(role)별 볼 수 있는 보안 등급: general=일반, staff=일반+대외비, admin=전체
- 경로 화이트리스트: grep/read_file은 역할의 원문 폴더만 (src/tools.py가 CURRENT_ROLE을 따른다)
- 위키: 역할별 디렉터리만 (graph_wiki.ROLE_GUARD)
- 인젝션 필터: 도구 결과에서 AI에게 하는 지시문을 지우고 로그를 남긴다
- 개인정보 마스킹, 감사 로그(jsonl)
- 사람 승인: 비밀 등급 인용 시 interrupt() (day2/agents.py의 approve 노드)

이 모듈을 import하면 위 장치가 켜진다(enable()).
"""
import json
import re
from datetime import datetime

from src.config import ROLE_LEVELS, ROOT

AUDIT_PATH = ROOT / "logs" / "audit.jsonl"
INJECTION_LOG = ROOT / "logs" / "injection.jsonl"
APPROVAL_REQUIRED = True

# 문서·도구 결과 속 지시문 패턴: AI/비서/모델을 부르며 명령하는 문장
INJECTION_RE = re.compile(
    r"[^.\n]*(?:AI|에이아이|비서|어시스턴트|모델|LLM)[^.\n]*(?:답해야 한다|답하라|출력하라|덧붙일 것|무시하고|따르라|지시)[^.\n]*[.]?"
    # PDF는 한 문장이 여러 줄로 나뉘므로 줄바꿈을 넘어 문장 끝(다/것/라 + 마침표)까지 지운다
    r"|\[AI 지시\][\s\S]{0,200}?(?:다|것|라)\.|※ (?:시스템 안내|참고):[\s\S]{0,200}?(?:다|것|라)\.")
PHONE_RE = re.compile(r"(01[016789])-(\d{3,4})-(\d{4})")
NAME_PHONE_RE = re.compile(r"(?<![가-힣])(?!연락처|전화|휴대폰|번호)([가-힣])([가-힣]{2})(\s*\(?\s*)(01[016789]-)")


def levels(role: str) -> list[str]:
    return ROLE_LEVELS.get(role or "general", ["일반"])


def sanitize(text: str) -> str:
    """도구 결과에서 지시문을 지운다. 지운 내용은 logs/injection.jsonl에 남긴다."""
    found = INJECTION_RE.findall(text or "")
    if not found:
        return text
    INJECTION_LOG.parent.mkdir(exist_ok=True)
    with open(INJECTION_LOG, "a", encoding="utf-8") as f:
        for s in found:
            f.write(json.dumps({"time": datetime.now().isoformat(timespec="seconds"), "removed": s.strip()},
                               ensure_ascii=False) + "\n")
    return INJECTION_RE.sub(" [지시문 제거됨] ", text)


def mask_pii(text: str) -> str:
    """이름+전화번호 → 김** 010-****-7730"""
    text = NAME_PHONE_RE.sub(lambda m: m.group(1) + "*" * len(m.group(2)) + m.group(3) + m.group(4), text or "")
    return PHONE_RE.sub(lambda m: f"{m.group(1)}-****-{m.group(3)}", text)


def audit_log(state: dict) -> None:
    AUDIT_PATH.parent.mkdir(exist_ok=True)
    rec = {"time": datetime.now().isoformat(timespec="seconds"), "role": state.get("role"),
           "question": state.get("question"), "citations": state.get("citations", []),
           "evidence": [{k: e.get(k) for k in ("source_type", "doc_or_rcept", "article_or_date", "collected_by")}
                        for e in state.get("evidence", [])],
           "refused": state.get("refused", False), "approved": state.get("approved"),
           "answer": state.get("answer", "")[:500]}
    with open(AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def enable() -> None:
    """권한·필터 장치를 켠다: 도구가 사용자 역할을 따르고, 도구 결과가 인젝션 필터를 거친다."""
    from src import tools
    from src.graphs import graph_agentic, graph_wiki
    graph_agentic.ROLE_GUARD = True
    graph_wiki.ROLE_GUARD = True
    if sanitize not in tools.OUTPUT_FILTERS:
        tools.OUTPUT_FILTERS.append(sanitize)


enable()
