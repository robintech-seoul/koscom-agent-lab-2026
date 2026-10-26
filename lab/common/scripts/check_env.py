"""환경 점검 (1-1 시작 전): 파이썬 패키지, 키, 임베딩 모델, 데이터, Claude Code, LLM 호출

python common/scripts/check_env.py      (저장소 루트에서, .venv를 켠 상태로)

처음 실행할 때 수업 폴더 경로 설정(.venv의 koscom_lab.pth)도 설치한다.
"""
import importlib
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "common"))
ok = True


def check(name, cond, hint=""):
    global ok
    print(f"{'[OK] ' if cond else '[X]  '} {name}" + ("" if cond else f"  → {hint}"))
    ok &= bool(cond)


check("Python 3.12 이상", sys.version_info >= (3, 12), "Python 3.12를 설치한다")
in_venv = sys.prefix != sys.base_prefix
check("가상환경(.venv) 켜짐", in_venv, ".venv\\Scripts\\activate (Mac: source .venv/bin/activate)")
if in_venv:
    import labpath  # noqa: E402
    pth = labpath.install()
    check("수업 폴더 경로 설정 (.venv의 koscom_lab.pth)", pth.exists(), "python common/labpath.py")
for mod in ("langgraph", "langchain_anthropic", "ragas", "chromadb", "kiwipiepy", "rank_bm25",
            "sentence_transformers", "mcp", "langchain_mcp_adapters", "pypdf", "docx"):
    try:
        importlib.import_module(mod)
        check(f"패키지 {mod}", True)
    except Exception as e:  # noqa: BLE001
        check(f"패키지 {mod}", False, f"uv pip install --no-deps -r requirements.lock ({type(e).__name__})")

from src.config import EMBED_MODEL_DIR  # noqa: E402

check(".env의 BIZROUTER_API_KEY", os.environ.get("BIZROUTER_API_KEY"), ".env.example을 .env로 복사하고 키를 넣는다")
check("DART_API_KEY (없으면 mock으로 실습)", True if os.environ.get("DART_API_KEY") else True)
check("임베딩 모델 models/KURE-v2", (EMBED_MODEL_DIR / "model.safetensors").exists(),
      "hf download nlpai-lab/KURE-v2 --local-dir models/KURE-v2 (또는 강사가 배포한 폴더 복사)")
check("규정 원문 data/raw (PDF·HWPX·DOCX 20개)",
      len([p for p in (ROOT / "data" / "raw").rglob("*") if p.suffix in (".pdf", ".hwpx", ".docx")]) == 20, "저장소를 다시 받는다")
check("bash (Windows는 Git Bash, 헤드리스 .sh 실행용)", shutil.which("bash"), "Git for Windows를 설치한다")
check("평가셋 eval/questions.jsonl (30건)", sum(1 for _ in open(ROOT / "eval" / "questions.jsonl", encoding="utf-8")) == 30)
check("Claude Code (claude 명령)", shutil.which("claude"), "npm install -g @anthropic-ai/claude-code")

if os.environ.get("BIZROUTER_API_KEY"):
    try:
        from src.config import get_llm
        r = get_llm(max_tokens=20).invoke("'준비 완료'라고만 답해")
        check(f"LLM 호출 (응답: {r.text.strip()[:20]})", True)
    except Exception as e:  # noqa: BLE001
        check("LLM 호출", False, str(e)[:120])
if shutil.which("claude"):
    sys.path.insert(0, str(ROOT / "scripts"))
    from claude_headless import run_claude
    d, _ = run_claude("'준비 완료'라고만 답해", ["Read"], timeout=180)
    check("Claude Code 헤드리스 (구독 계정)", not d.get("is_error"), str(d.get("result", ""))[:200])
check("원문 옆 텍스트 사본 (.txt)", len(list((ROOT / "data" / "raw").rglob("*.txt"))) == 20,
      "python scripts/make_raw_text.py")
check("리랭커 모델 models/mmarco-mMiniLMv2 (1-3 선택)", (ROOT / "models" / "mmarco-mMiniLMv2" / "config.json").exists(),
      "hf download cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 --local-dir models/mmarco-mMiniLMv2")
if sys.platform == "win32":
    check("UTF-8 모드 (PYTHONUTF8=1)", sys.flags.utf8_mode, "PowerShell에서 setx PYTHONUTF8 1 실행 후 터미널을 새로 연다")
print("\n모두 통과" if ok else "\n[X] 항목을 해결한 뒤 다시 실행한다")
