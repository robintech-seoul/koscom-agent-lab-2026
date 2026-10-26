"""수업 번호 폴더에서 python을 실행하면, 그 수업까지의 폴더와 common/을 모듈 검색 경로에 넣는다.

예: 1027/1-3/에서 `python -m src.run_eval` → 검색 순서 1-3, 1-2, 1-1, common
    → 1-3의 src/graphs/graph_rag.py, 1-2의 src/run_eval.py, common의 src/config.py를 함께 쓴다.
    같은 이름의 파일이 여러 수업에 있으면 가까운(나중) 수업의 것을 쓴다 (2-2의 graph_rag.py가 1-3의 것보다 먼저).

가상환경(.venv)에 koscom_lab.pth 를 두면 python이 시작할 때마다 setup()이 자동으로 실행된다.
설치: python common/labpath.py  (SETUP.md 참고)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SESSIONS = [("1027", s) for s in ("1-1", "1-2", "1-3", "2-1", "2-2", "2-3", "hw1")] + \
           [("1028", s) for s in ("3-1", "3-2", "3-3", "4-1", "4-2", "4-3", "hw2")]


def chain(cwd: Path) -> list[Path]:
    """cwd가 속한 수업 폴더부터 1-1까지(역순), 마지막에 common."""
    try:
        parts = cwd.resolve().relative_to(ROOT).parts
    except ValueError:
        return []
    out = []
    if len(parts) >= 2 and (parts[0], parts[1]) in SESSIONS:
        i = SESSIONS.index((parts[0], parts[1]))
        out = [ROOT / d / s for d, s in reversed(SESSIONS[:i + 1])]
    return out + [ROOT / "common"]


def setup() -> None:
    paths = [str(p) for p in chain(Path.cwd())]
    for p in reversed(paths):
        if p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)


def install() -> Path:
    """현재 python(가상환경)의 site-packages에 koscom_lab.pth를 쓴다."""
    import sysconfig
    pth = Path(sysconfig.get_paths()["purelib"]) / "koscom_lab.pth"
    pth.write_text(f"{ROOT / 'common'}\nimport labpath; labpath.setup()\n", encoding="utf-8")
    return pth


if __name__ == "__main__":
    if sys.prefix == sys.base_prefix:
        sys.exit("가상환경이 켜져 있지 않다. .venv를 켠 뒤 다시 실행한다 (SETUP.md 3절)")
    print("설치:", install())
