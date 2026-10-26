"""data/raw/, data/updates/의 PDF·HWPX·DOCX마다 같은 폴더에 같은 이름의 텍스트 사본(.txt)을 만든다.

Claude Code의 Grep은 PDF·HWPX·DOCX 안을 검색하지 못하고 Read는 HWPX·DOCX를 열지 못한다.
사본이 원문 옆에 있으면 "data/raw/ 폴더만 사용해서 답해줘"(2-3), "data/raw/의 문서를 ingest"(과제 1),
"data/updates/를 ingest"(4-3) 지시문을 교재 그대로 쓸 수 있다.
python scripts/make_raw_text.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.ingest import read_lines  # noqa: E402

for src_dir in (ROOT / "data" / "raw", ROOT / "data" / "updates"):
    for p in sorted(src_dir.rglob("*")):
        if p.suffix in (".pdf", ".docx", ".hwpx"):
            out = p.with_suffix(".txt")
            out.write_text(f"[원본 파일: {p.relative_to(ROOT).as_posix()}의 텍스트 사본]\n" + "\n".join(read_lines(p)) + "\n",
                           encoding="utf-8")
            print(out.relative_to(ROOT).as_posix())
