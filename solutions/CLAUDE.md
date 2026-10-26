# CLAUDE.md — koscom-agent-lab

RAG 기반 Multi-AI Agent 실습 저장소. Claude Code는 코드를 만들기 전에 이 파일을 먼저 읽는다.

## 1. 고정 버전과 실행 환경

- 실습 PC는 **Windows**다. Python 3.12, 가상환경 `.venv` (`uv venv` + `uv pip install -r requirements.lock`)
- Claude Code 헤드리스 실행 스크립트(`scripts/run_claude_*.sh`)는 bash로 만든다. Windows에서는 **Git Bash**로 실행한다(`bash scripts/run_claude_baseline.sh`).
  스크립트 안에서는 저장소 루트로 이동해 `claude -p`를 실행한다(그래야 `data/regs_all.md` 같은 경로가 맞는다).
- 그 밖의 스크립트와 모듈은 Python으로 만든다. 경로는 `pathlib`로 다룬다.
- **파일을 열 때는 항상 `encoding="utf-8"`을 지정한다.** Windows 기본 인코딩(cp949)으로 열면 한글 JSON에서 오류가 난다. subprocess 출력도 `encoding="utf-8"`.
- 주요 패키지 (requirements.lock에 고정)
  - langgraph 1.2.x, langchain 1.4.x, langchain-anthropic 1.7.x, langchain-core 1.7.x
  - langchain-mcp-adapters 0.3.x, mcp 1.30.x (FastMCP 포함)
  - ragas 0.4.3 (langchain-community 0.4.1과 함께 써야 import 오류가 나지 않는다)
  - chromadb 1.5.x, kiwipiepy 0.24.x, rank-bm25 0.2.2, sentence-transformers 6.x
- 실행은 **수업 번호 폴더**(예: `1027/1-3/`)에서 모듈로: `python -m src.run_eval ...`, `python -m day2.agents ...`

## 1.1 폴더 구조 (중요)

```
<저장소 루트>/            CLAUDE.md, .env, .venv/, models/, data/, eval/, logs/, wiki/  ← 모든 수업이 함께 쓴다
├─ common/               처음부터 주는 코드: src/config.py, src/graphs/sample_graph.py, scripts/check_env.py 등
├─ 1027/1-1/ … hw1/      수업마다 그 시간에 만드는 코드 (src/, scripts/, day2/)
└─ 1028/3-1/ … hw2/
```

- **새 파일은 지금 수업 번호 폴더 안에 만든다.** 예: 1-3에서 "src/retriever.py를 만들어줘" → `1027/1-3/src/retriever.py`. 예외: 위키(`wiki/` 아래 페이지와 `SCHEMA.md`)는 모든 수업이 함께 쓰는 데이터라 저장소 루트의 `wiki/`에 만든다.
- **`data/`, `eval/`, `wiki/`, `logs/`는 저장소 루트에 있다.** 지시문의 `data/regs_all.md`, `data/raw/`, `eval/questions.jsonl`, `eval/results/`는 수업 폴더에서 보면 `../../data/...`, `../../eval/...`이다. 수업 폴더 안에 `data/`나 `eval/`을 새로 만들지 않는다.
- **앞 수업의 코드는 앞 수업 폴더에 있다.** 예: 1-3에서 쓰는 `src/run_eval.py`는 `1027/1-2/src/run_eval.py`, `src/config.py`는 `common/src/config.py`. 고칠 때는 지금 수업 폴더로 복사한 뒤 고친다(예: 2-2에서 `1027/1-3/src/graphs/graph_rag.py`를 `1027/2-2/src/graphs/`로 복사).
- 수업 폴더에서 `python -m src.…`을 실행하면 그 수업, 앞 수업들(가까운 순), `common/` 순으로 모듈을 찾는다(`common/labpath.py`). 같은 이름이면 가까운 수업의 파일을 쓴다.
- **`__init__.py`를 만들지 않는다.** `src/`, `src/graphs/`, `day2/`, `scripts/`는 여러 수업 폴더에 나뉘어 있는 패키지라, `__init__.py`가 하나라도 생기면 다른 수업의 모듈을 찾지 못한다.
- 코드 안에서 데이터 경로는 `src.config`의 `ROOT`, `DATA`, `EVAL`, `RESULTS` 등을 쓴다. 명령줄로 받은 상대 경로는 `root_path()`로 바꾼다.

## 2. 모델 (모든 실습에서 같은 모델로 고정)

| 용도 | 값 |
|---|---|
| 메인 LLM (그래프, 채점) | `anthropic/claude-haiku-5.5` (BizRouter) |
| Claude Code 헤드리스 (기준선, 직접 탐색) | `claude-haiku-5-5` — 같은 Haiku 5.5. 각자 로그인한 Claude 구독 계정으로 실행 |
| 접속 | LangChain은 BizRouter `base_url="https://api.bizrouter.ai"`, 키는 환경 변수 `BIZROUTER_API_KEY` |
| 임베딩 | 로컬 `models/KURE-v2` (sentence-transformers, 인터넷 불필요) |
| 리랭커 (1-3, 선택) | 로컬 `models/mmarco-mMiniLMv2` (sentence-transformers `CrossEncoder`, 약 470MB) |
| 단가 (USD / 100만 토큰) | 입력 0.1, 출력 0.5, 캐시 읽기 0.01, 캐시 쓰기 0.125 (Haiku 5.5, BizRouter) |

- LLM은 반드시 `src/config.py`의 `get_llm()`으로 만든다. 모델 이름을 코드에 따로 적지 않는다.
- **구조화 출력은 `llm.with_structured_output(Schema, method="json_schema")`로 쓴다.**
  이 모델은 `tool_choice`를 강제하는 기본 방식(function calling)을 지원하지 않아 400 오류가 난다.
- Claude Code 헤드리스 실행은 `scripts/run_claude_*.sh`(bash) 또는 `scripts/claude_headless.py`의 `run_claude(prompt, allowed_tools)`를 쓴다.
  - `claude -p --model claude-haiku-5-5 --output-format json --allowedTools ... --setting-sources project`
  - **Claude Code(기준선, 직접 탐색 포함)는 반드시 로그인한 구독 계정으로 실행한다. `ANTHROPIC_API_KEY`·`ANTHROPIC_BASE_URL`을 붙이지 않는다(API 과금 금지).**
  - 프롬프트는 **표준 입력**으로 넘긴다(Windows의 claude.cmd는 여러 줄 인자를 망가뜨린다).
  - `to_result(q, d, latency, method)`가 출력 JSON을 결과 파일 한 줄로 바꾼다.
  - `--output-format json` 출력 필드: `result`(답변), `usage.input_tokens`, `usage.output_tokens`,
    `usage.cache_read_input_tokens`, `usage.cache_creation_input_tokens`, `total_cost_usd`, `duration_ms`, `num_turns`, `is_error`

## 3. 데이터와 경로

- `data/raw/{public,internal,secret}/` — 규정 원문(PDF 10, DOCX 7, HWPX 3). 폴더가 보안 등급이다: public=일반, internal=대외비, secret=비밀
- 원문마다 같은 폴더에 같은 이름의 텍스트 사본(`.txt`)이 있다. **Claude Code가 원문을 직접 읽거나 검색할 때는 이 `.txt`를 쓴다**(Grep은 PDF·HWPX·DOCX 안을 못 찾고, Read는 HWPX·DOCX를 못 연다). 적재(`src/ingest.py`)는 `.txt`를 건너뛴다
- HWPX(한글 문서)는 zip 안의 `Contents/section0.xml`에 문단 `<hp:p>`와 글자 `<hp:t>`가 들어 있다
- `data/regs_all.md` — 기준선용. 전체 규정을 하나로 합친 파일
- `data/parsed/articles.jsonl` — 조항 단위 적재 결과 (1-2에서 생성)
- `data/updates/` — 4-3용 신규·개정·폐지 문서 (여기도 원문 옆에 `.txt` 사본)
- `eval/questions.jsonl` — 본 평가셋 30건. `eval/sets/`에 문서 밖 10, 결합 10, DART 10, 공격 5
- `eval/human_labels.csv` — 사람 채점 10건
- 역할(role)과 읽을 수 있는 등급: `general`=일반, `staff`=일반+대외비, `admin`=전체

### 조항 레코드 (`data/parsed/articles.jsonl` 한 줄)
```json
{"chunk_id": "HB-OPS-001_r2_제12조", "doc": "시세정보전송규정", "doc_no": "HB-OPS-001",
 "article": "제12조", "title": "전송 지연 시 통보", "text": "...",
 "effective_date": "2026-03-01", "security_level": "일반", "revision": 2,
 "status": "current", "source_path": "data/raw/public/시세정보전송규정_r2.pdf"}
```

### 결과 파일 형식 (`eval/results/<name>_r<n>.jsonl` 한 줄 = 질문 1건)
```json
{"id": "Q07", "type": "trap_revision", "question": "...", "answer": "...",
 "citations": [{"doc": "시세정보전송규정", "article": "제12조", "effective_date": "2026-03-01"}],
 "contexts": ["검색된 조항 원문 ..."], "refused": false,
 "input_tokens": 3120, "output_tokens": 210, "cost_usd": 0.0083, "latency_s": 4.1,
 "tool_calls": [{"tool": "grep", "args": {"pattern": "15초"}, "result_len": 812}],
 "method": "rag", "model": "anthropic/claude-haiku-5.5"}
```
- 모든 방식(기준선, RAG, 에이전틱, 위키, 단일, 멀티)이 이 형식을 쓴다. 채점도 같은 스크립트로 한다.

### 그래프 모듈 규칙
- 그래프 모듈은 `build_graph()`를 내보낸다. 입력 state는 `{"question": str, "role": str}`.
- 출력 state에 `answer`, `citations`, `contexts`, `refused`(선택), `tool_log`(선택)를 둔다.

## 4. LangGraph 1.x API 예시 (이 형태만 쓴다)

```python
from typing import Annotated, TypedDict
import operator
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages          # 메시지 리스트 reducer
from langgraph.prebuilt import ToolNode                    # 도구 실행 노드
from langgraph.types import Send, interrupt, Command       # 병렬 분기, 사람 승인, 재개
from langgraph.checkpoint.memory import InMemorySaver      # interrupt에 필요

class State(TypedDict):
    question: str
    messages: Annotated[list, add_messages]
    evidence: Annotated[list[dict], operator.add]          # 여러 노드 결과를 이어 붙임
    answer: str

g = StateGraph(State)
g.add_node("retrieve", retrieve)
g.add_node("generate", generate)
g.add_edge(START, "retrieve")
g.add_edge("retrieve", "generate")
g.add_conditional_edges("generate", route_fn, {"ok": END, "refuse": "refuse"})   # 조건부 엣지
graph = g.compile()                                       # interrupt를 쓰면 compile(checkpointer=InMemorySaver())

# 병렬 분기: 조건부 엣지 함수가 Send 리스트를 돌려준다
def fan_out(state): return [Send("research", {"topic": t}) for t in state["topics"]]

# 사람 승인: 노드 안에서 interrupt(), 재개는 Command(resume=...)
def approve(state):
    decision = interrupt({"question": "비밀 등급 인용 승인?", "citations": state["citations"]})
    return {"approved": decision == "yes"}
# graph.invoke(inp, config={"configurable": {"thread_id": "t1"}})
# graph.invoke(Command(resume="yes"), config={"configurable": {"thread_id": "t1"}})
```

- 쓰지 말 것 (옛 API): `langgraph.prebuilt.create_react_agent`(1.x에서 폐기 예정), `MessageGraph`, `set_entry_point`, `langchain.agents.AgentExecutor`
- 토큰 집계는 `langchain_core.callbacks.get_usage_metadata_callback()`으로 감싼다.

## 5. 금지 사항

- `eval/questions.jsonl`, `eval/sets/`, `eval/human_labels.csv`를 수정하지 않는다.
- `data/raw/`를 수정하지 않는다.
- API 키를 코드나 로그에 적지 않는다. `.env`에서 읽는다.
- 평가셋 정답(gold_*)을 그래프 프롬프트에 넣지 않는다.
