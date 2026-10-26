# koscom-agent-lab-2026/solutions — RAG 기반 Multi-AI Agent 만들기 실습 정답

코스콤 과정 1(2026-10-27 ~ 28)의 실습 자료를 수업 시간 단위로 정리한 폴더입니다. 기준은 의뢰처에 보낸 교재(슬라이드 PDF, 2026-10-20판)입니다. 각 세션 폴더의 README는 교재의 실습 지시문, 확인 기준, 막힐 때를 그대로 옮겼습니다.

기법별 실행 결과는 [RESULTS.md](RESULTS.md)에 정리했습니다.

## 1. 폴더 구성

```
koscom-agent-lab-2026/solutions/
├─ README.md, RESULTS.md, SETUP.md
├─ CLAUDE.md                 Claude Code 프로젝트 규칙. 수업 폴더에서 열어도 위쪽의 이 파일을 읽는다
├─ .env.example, .gitignore, requirements.in, requirements.lock, requirements-optional.txt
├─ .env, .venv/, models/     각자 만든다 (git에 올리지 않음)
├─ common/                   처음부터 주는 코드
├─ data/                     규정 원문, DART 녹화 응답, 미리 만든 위키 (모든 수업이 함께 씀)
├─ eval/                     평가셋, 결과 파일 eval/results/ (모든 수업이 함께 씀)
├─ 1027/                     1일차: 1-1 1-2 1-3 2-1 2-2 2-3 hw1
└─ 1028/                     2일차: 3-1 3-2 3-3 4-1 4-2 4-3 hw2
```

**common/**

| 경로 | 내용 |
|---|---|
| `labpath.py` | 수업 폴더에서 python을 실행할 때 앞 수업 폴더와 common을 모듈 경로에 넣는다 (2절) |
| `src/config.py` | 경로, 모델, 단가, .env 읽기. 모든 수업 코드가 import한다 |
| `src/demo_langgraph.py` | 1-1 강사 LangGraph 시연 |
| `src/graphs/sample_graph.py` | 1-2 평가 러너 확인용 샘플 그래프 (교재의 "solutions의 샘플 그래프") |
| `scripts/check_env.py` | 환경 점검. 처음 실행할 때 `labpath` 설정도 설치한다 |
| `scripts/claude.py`, `claude_headless.py` | Claude Code 실행(고정 모델, 구독 계정), 헤드리스 공용 함수 |
| `scripts/make_raw_text.py` | 원문 옆 .txt 사본 생성 (이미 만들어져 있음. 강사용) |

**data/, eval/**

| 경로 | 내용 |
|---|---|
| `data/raw/{public,internal,secret}/` | 가상 회사 한빛시장정보(주)의 규정 원문 20개 (PDF 10, DOCX 7, HWPX 3). 폴더가 보안 등급: public=일반, internal=대외비, secret=비밀. 원문마다 같은 이름의 텍스트 사본(.txt)이 옆에 있다 |
| `data/updates/` | 4-3용 신규 1, 개정 2, 폐지 1 (텍스트 사본 포함) |
| `data/regs_all.md` | 1-1 기준선용. 규정 20개를 하나로 합친 파일 (약 6만 토큰) |
| `data/parsed/articles.jsonl` | 1-2 적재 결과 (조항 272개) |
| `data/companies.json`, `data/dart_cache/` | 3-1 가상 회사 A사, B사와 DART 녹화 응답 |
| `data/wiki/`, `data/wiki_updated/` | 과제 1, 4-3용 미리 만든 위키 (교재: "나머지는 미리 만든 위키로 채운다") |
| `eval/questions.jsonl` | 평가셋 30건 (단일 10, 교차 참조 5, 종합 5, 개정 함정 4, 표현 변형 함정 3, 권한 밖 3) |
| `eval/sets/` | 문서 밖 10, 결합 10, DART 10, 공격 5, 개정 반영 4 |
| `eval/human_labels.csv` | 2-1 사람 채점 10건 |
| `eval/results/` | 강사가 돌린 결과 파일. 뒤 수업의 비교 스크립트가 앞 수업 결과를 여기서 읽는다 |

**수업 폴더** (예: `1027/1-3/`)

| 항목 | 내용 |
|---|---|
| `README.md` | 그 시간에 할 실습, 교재 지시문, 확인 기준, 작성할 표 |
| `src/`, `day2/`, `scripts/`, `wiki/` | 그 시간에 Claude Code로 만드는 파일의 정답 |
| `results/` | 정답 코드를 실제로 실행한 기록. `<단계>.log`(첫 줄이 명령)와 그때의 결과 파일 |

- 한 파일이 나중 수업에서 다시 바뀌면 각 수업 폴더에 그 시점의 판이 있다. `graph_rag.py`는 1-3판(인용을 본문에서 추출)과 2-2판(구조화 출력, 거부), `agents.py`는 3-2판(순차), 3-3판(evidence 공유, 병렬), hw2판(공지 담당 추가).

## 2. 실행하기

준비는 [SETUP.md](SETUP.md)를 따른다(.venv, .env, models, 환경 점검). 그 뒤에는 **수업 폴더에 들어가서** 교재 명령을 그대로 실행한다.

```powershell
cd 1027\1-3
python -m src.compare_retrieval --detail
python -m src.run_eval --graph src.graphs.graph_rag --name rag
```

- **앞 수업 코드는 자동으로 찾는다.** 1-3에서 실행하면 1-3, 1-2, 1-1, common 순으로 모듈을 찾는다(`common/labpath.py`, .venv에 설치되는 `koscom_lab.pth`). 그래서 1-3의 `graph_rag.py`는 1-2의 `run_eval.py`와 common의 `config.py`를 복사 없이 함께 쓴다. 같은 이름의 파일은 가까운 수업 것을 쓴다(2-2 이후에는 2-2의 `graph_rag.py`, 4-2에서는 3-3의 `agents.py`).
- **데이터와 결과는 루트 한 벌을 함께 쓴다.** 코드는 `src.config`의 `ROOT`(이 폴더) 기준으로 `data/`, `eval/`을 찾는다. 명령줄의 `eval/sets/…`, `eval/results/…` 같은 상대 경로도 수업 폴더에 없으면 루트에서 찾는다.
- **Claude Code도 수업 폴더에서 연다.** 위쪽의 `CLAUDE.md`를 읽고, 교재 지시문의 `data/regs_all.md` 같은 경로를 루트에서 찾는다(1-1 실습 ①을 `1027/1-1`에서 실제로 확인). `.sh` 스크립트는 안에서 루트로 이동해 `claude -p`를 실행한다.
- **`__init__.py`를 만들지 않는다.** `src/`, `day2/`가 여러 수업 폴더에 나뉘어 있어서, 하나라도 생기면 다른 수업의 모듈을 찾지 못한다.
- 각 수업의 확인 명령은 그 수업 `results/*.log` 첫 줄(`$ ...`)에 있다. 그 기록은 예전 구조에서 돌린 것이라 일부 경로가 다르다: `solutions.graphs.sample_graph` → `src.graphs.sample_graph`, `solutions/wiki` → `data/wiki`, `solutions/wiki_updated` → `data/wiki_updated`, 위키 ingest의 `sys.path.insert(0,'scripts')` → `sys.path.insert(0,'../../common/scripts')`.

## 3. 모델과 비용

| 용도 | 모델 | 과금 |
|---|---|---|
| 그래프, RAGAS 채점 | `anthropic/claude-haiku-5.5` (BizRouter) | API. 입력 0.1달러, 출력 0.5달러 / 100만 토큰 |
| Claude Code 헤드리스 (1-1 기준선, 2-3 직접 탐색, 과제 1·4-3 위키 ingest·lint) | `claude-haiku-5-5` | **Claude 구독 계정**. API 키를 쓰지 않는다 |
| 임베딩 | KURE-v2 (로컬, 약 300MB) | 없음 |
| 리랭커 (1-3) | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (로컬, 약 470MB) | 없음 |

## 4. 교재와 맞추기 위해 실습 쪽에서 바꾼 것

교재(2026-10-20판)는 고치지 않고, 실습 코드와 데이터를 교재에 맞췄습니다.

| 교재 내용 | 실습 쪽 조치 |
|---|---|
| 1-1, 2-3: `scripts/run_claude_*.sh` | bash 스크립트로 만들었다. Windows는 Git Bash로 실행 (`bash scripts/run_claude_baseline.sh`) |
| 1-2: PDF·HWPX·DOCX 파싱 | 규정 3개(종목정보변경절차, 업무연속성계획, 침해사고대응절차)를 HWPX로 바꿨다. 적재 결과는 DOCX일 때와 조항 272개 모두 같다 |
| 1-2: "solutions의 샘플 그래프로 러너 확인" | `common/src/graphs/sample_graph.py`를 넣었다 (`--graph src.graphs.sample_graph`) |
| 1-3: 리랭커 적용 전후, "하이브리드가 벡터보다 많이 적중" | 작은 리랭커(약 470MB)를 넣었다. 하이브리드+리랭커 27/27, 벡터 26/27로 기준 충족 |
| 2-3, 과제 1, 4-3: Claude Code가 `data/raw/`, `data/updates/`를 직접 읽음 | 원문 옆에 텍스트 사본(.txt)을 두었다. Claude Code의 Grep은 PDF·HWPX·DOCX 안을 못 찾고, Read는 HWPX·DOCX를 못 열기 때문 |
| 3-2 → 3-3: evidence 공유와 Send 병렬은 3-3에서 추가 | 3-2판 `agents.py`는 순차 실행·중복 제거 없음, 3-3판에서 병렬·중복 제거 |
| 4-2: `guard.py`는 4-2에서 만든다 | 3-2판·3-3판은 guard 없이 동작하고, 4-2에서 `guard.py`가 들어오면 켜진다 |

## 5. 교재대로 할 수 없거나 확인이 필요한 것

| 교재 내용 | 상황 |
|---|---|
| `git checkout s1-1-start`, `s1-2-done` (태그) | 태그는 쓰지 않는다. 늦어진 수강생은 해당 수업 폴더의 정답 파일로 맞춘다 |
| "막힐 때 → solutions/…, 정답의 …" | `solutions/<날짜>/<수업>/` 아래 같은 위치의 파일이 정답이다. 각 수업 README의 막힐 때에 실제 위치를 적었다 |
| 4-1 Phoenix (선택) | 실행하지 않았다. 강사 시연 또는 생략 |
| 3-3 공유 위키 비교 (선택) | 구현하지 않았다 |
| 4-2 지시문의 `user_role` | 정답 코드는 state 키 이름을 `role`로 쓴다. 동작은 같다 |
| HWPX 파일 | 파싱은 확인했지만 한글 프로그램으로 열리는지는 확인하지 못했다 |
| Windows | 실제 Windows PC에서 실행해 보지 않았다 (Mac에서 확인). 특히 .venv의 `koscom_lab.pth` 설치와 Git Bash에서의 `.sh` 실행 |
| 4-1 `day2.tracing` | 선택 패키지(`requirements-optional.txt`)가 없으면 import 오류. 설치 후 실행 |
