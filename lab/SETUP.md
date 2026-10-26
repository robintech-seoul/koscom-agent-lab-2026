# 실습 환경 준비

실습을 시작하기 전에 한 번 해 둡니다. 기준은 Windows PowerShell이고, Mac은 각 단계 끝의 안내를 따릅니다.
1~6단계의 명령은 저장소 루트(이 `SETUP.md`가 있는 폴더)에서 실행합니다. 실습 중에는 수업 번호 폴더(예: `1027\1-3`)로 들어가서 실행합니다(7단계).

준비가 끝나면 아래 상태가 됩니다.

- uv, Git(Git Bash), Claude Code가 설치되어 있다
- 루트의 `.venv`에 Python 3.12와 실습 패키지가 들어 있다
- 루트의 `.env`에 BizRouter 키가 들어 있다
- 루트의 `models/`에 임베딩 모델과 리랭커 모델이 있다
- `python common\scripts\check_env.py`가 "모두 통과"를 출력한다

## 1. 도구 설치 (PC마다 한 번)

PowerShell을 열고 실행합니다.

```powershell
winget install astral-sh.uv      # Python 설치, 가상환경, 패키지 설치를 모두 uv로 한다
winget install Git.Git           # git과 Git Bash (.sh 스크립트 실행용)
setx PYTHONUTF8 1                # 한글 파일 인코딩 오류 방지
```

- 설치가 끝나면 **PowerShell을 닫고 새로 엽니다.** 그래야 `uv`, `git` 명령과 `PYTHONUTF8` 설정이 적용됩니다.
- Python은 따로 설치하지 않습니다. 3단계에서 uv가 Python 3.12를 받아 씁니다. PC에 이미 설치된 Python과 섞이지 않습니다.

Claude Code를 설치하고 로그인합니다.

```powershell
irm https://claude.ai/install.ps1 | iex
claude                           # 처음 실행하면 로그인 안내가 나온다. 각자 Claude 계정으로 로그인
```

- Claude Code는 **각자 로그인한 Claude 구독 계정으로만** 씁니다. 환경 변수 `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`을 설정하지 않습니다. 설정되어 있으면 API 요금이 나갑니다.
- **Claude Code 설치나 로그인이 안 되면** Claude 데스크톱 앱으로 실습합니다. 지시문을 앱에 넣어 코드를 만들고, 그 코드를 수업 폴더에 파일로 저장합니다. 헤드리스 실행(1-1 실습 ②, 2-3 실습 ②)만 할 수 없고, 그 결과는 강사 결과 파일(`solutions/…/results/`)을 씁니다. 6단계 점검에서 Claude Code 항목은 `[선택]`으로 표시되고 통과에는 영향이 없습니다.

확인:

```powershell
uv --version
git --version
claude --version
```

> Mac: `brew install uv git` (또는 `curl -LsSf https://astral.sh/uv/install.sh | sh`), Claude Code는 `curl -fsSL https://claude.ai/install.sh | bash`. `setx`는 필요 없습니다.

## 2. 저장소 루트로 이동

```powershell
cd <저장소 경로>\koscom-agent-lab-2026\lab
```

- 경로에 한글이나 공백이 없는 곳이 안전합니다. 예: `C:\work`
- 6단계까지는 이 폴더에서 실행합니다.

## 3. 가상환경 만들기 (실습 폴더마다 한 번)

```powershell
uv venv --python 3.12 .venv
uv pip install -r requirements.lock
```

- `.venv` 폴더가 저장소 루트에 생깁니다. 모든 수업 폴더가 이 하나를 함께 씁니다. 실습에 필요한 패키지는 모두 여기에만 설치됩니다.
- 설치량은 약 1.4GB입니다(torch 포함). 교육장 네트워크에 따라 수 분이 걸립니다.
- `requirements.lock`에 패키지 버전이 고정되어 있어서 모든 PC에 같은 버전이 설치됩니다. 패키지를 따로 `pip install` 하지 않습니다.
- `.venv`는 배포하거나 git에 올리지 않습니다(`.gitignore`에 들어 있음). 문제가 생기면 `.venv` 폴더를 지우고 이 단계를 다시 실행합니다.

가상환경을 켭니다.

```powershell
.venv\Scripts\activate
```

- 프롬프트 앞에 `(.venv)`가 붙으면 켜진 것입니다. **PowerShell을 새로 열 때마다** 다시 켭니다.
- **`.venv`는 만든 폴더 전용입니다.** 실습은 `lab\.venv`만 켜고 합니다. `solutions`의 코드를 돌려 볼 때는 `solutions`에 `.venv`를 따로 만들어 켭니다. 한 번 켠 `.venv`는 `cd`로 다른 폴더에 가도 계속 켜져 있으므로, 다른 쪽 `.venv`를 켠 채 실행하면 앞 수업 코드를 못 찾거나 결과 파일이 다른 폴더의 `eval/results`에 쌓입니다. 헷갈리면 PowerShell을 새로 열고 실행할 쪽의 `.venv`를 켭니다.
- 지금 켜진 `.venv`가 어느 폴더 것인지 확인: `python -c "import sys; print(sys.prefix)"`
- "스크립트를 실행할 수 없습니다" 오류가 나면 한 번만 실행합니다: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

> Mac: `source .venv/bin/activate`

## 4. 키 넣기

```powershell
copy .env.example .env
notepad .env
```

`.env`에 아래 값을 넣고 저장합니다.

| 항목 | 필수 | 내용 |
|---|---|---|
| `BIZROUTER_API_KEY` | 필수 | 강사가 안내하는 BizRouter 키. 그래프와 채점에서 LLM을 부를 때 쓴다 |
| `DART_API_KEY` | 선택 | 3-1 공시 조회용. OpenDART에서 각자 발급(즉시 발급). 없으면 녹화 응답으로 실습한다 |

- `.env`는 다른 사람에게 보내거나 git에 올리지 않습니다.
- DART 키는 이용약관상 다른 사람과 나눠 쓸 수 없습니다. 쓰려면 각자 발급합니다.

> Mac: `cp .env.example .env`

## 5. 모델 넣기

임베딩 모델과 리랭커 모델을 루트의 `models/`에 넣습니다. 강사가 구글 드라이브로 공유한 `koscom_models.zip`(약 640MB)을 받아 저장소 루트(이 `SETUP.md`가 있는 폴더)에 풀면 `models/` 폴더가 생깁니다. 이 방법이 가장 빠릅니다.

```
models/KURE-v2/                  임베딩 모델 (약 300MB, 1-3부터 사용)
models/mmarco-mMiniLMv2/         리랭커 모델 (약 470MB, 1-3 리랭커 비교)
```

배포 파일이 없으면 직접 받습니다(가상환경을 켠 상태에서).

```powershell
hf download nlpai-lab/KURE-v2 --local-dir models/KURE-v2
hf download cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 --local-dir models/mmarco-mMiniLMv2
```

## 6. 환경 점검

```powershell
python common\scripts\check_env.py
```

처음 실행할 때 **수업 폴더 경로 설정**(`.venv` 안의 `koscom_lab.pth`)도 함께 설치합니다. 이 설정이 있어야 수업 폴더에서 앞 수업의 코드를 찾습니다. `.venv`를 새로 만들었으면 이 점검을 다시 실행합니다.

마지막 줄에 **모두 통과**가 나오면 준비가 끝났습니다. 점검하는 항목은 아래와 같습니다.

- Python 3.12 이상, 가상환경 켜짐, 수업 폴더 경로 설정, 주요 패키지 설치
- `.env`의 BizRouter 키, DART 키(없어도 통과)
- 모델 폴더 2개
- 규정 원문 20개, 텍스트 사본, 평가셋 30건
- bash(Git Bash)
- LLM 호출 1번
- (선택) Claude Code 설치와 헤드리스 실행 1번(구독 계정)

`[X]`가 나온 항목은 옆에 적힌 안내대로 해결한 뒤 다시 실행합니다.

## 7. 실행 방법 (실습 중 계속)

- **수업 번호 폴더로 들어가서 실행합니다.** 교재 명령을 그대로 씁니다.
  ```powershell
  cd 1027\1-3
  python -m src.run_eval --graph src.graphs.graph_rag --name rag
  ```
  앞 수업에서 만든 코드(1-2의 `run_eval.py` 등)와 `common/`의 `config.py`는 자동으로 찾습니다. 복사하지 않습니다.
- **데이터와 결과는 루트 한 벌을 함께 씁니다.** `data/`, `eval/`, `eval/results/`는 루트에 있고, 수업 폴더에서 `eval/sets/…`처럼 적어도 루트에서 찾습니다. 수업 폴더 안에 `data/`, `eval/`을 만들지 않습니다.
- `.sh` 스크립트는 **Git Bash**에서 수업 폴더로 들어가 실행합니다.
  ```bash
  cd 1027/1-1
  source ../../.venv/Scripts/activate
  bash scripts/run_claude_baseline.sh 1
  ```
- **Claude Code도 수업 폴더에서 `claude`로 엽니다.** 새 파일이 그 수업 폴더에 만들어지고, 위쪽의 `CLAUDE.md`(실습 규칙)를 읽습니다. 교재 지시문의 `data/regs_all.md` 같은 경로는 루트의 파일을 찾아 읽습니다.
- **`__init__.py`를 만들지 않습니다.** 하나라도 생기면 다른 수업 폴더의 코드를 찾지 못합니다.

## 8. 자주 나는 문제

| 증상 | 해결 |
|---|---|
| `uv`, `git`, `claude` 명령을 찾을 수 없음 | 설치 후 PowerShell을 새로 연다 |
| 한글 JSON을 읽다가 `UnicodeDecodeError` | `setx PYTHONUTF8 1` 실행 후 PowerShell을 새로 연다 |
| `ModuleNotFoundError: No module named 'src…'` | 수업 폴더 안에서 `python -m src.…` 형식으로 실행했는지 확인. 그래도 나면 `python common\scripts\check_env.py`를 다시 실행해 경로 설정을 설치하고, 수업 폴더에 `__init__.py`가 생겼으면 지운다 |
| 다른 폴더(예: solutions)의 코드가 실행됨, `[경고] 지금 켜진 .venv는 …용이다`가 나옴 | `.venv`는 그 폴더 전용이다. `lab`과 `solutions`는 각자 루트에 `.venv`를 따로 만들고, 실행하는 쪽의 `.venv`를 켠다 |
| 패키지가 없다는 오류 | 프롬프트 앞에 `(.venv)`가 있는지 확인. 없으면 `.venv\Scripts\activate` |
| LLM 호출에서 429 오류 | 여러 사람이 동시에 호출해 한도에 걸린 것. 잠시 뒤 다시 실행한다(코드가 자동으로 재시도한다) |
| Claude Code가 API 요금으로 실행됨 | `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL` 환경 변수를 지우고 `claude`에서 구독 계정으로 로그인한다 |
