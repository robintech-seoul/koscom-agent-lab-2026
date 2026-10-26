"""data/raw/의 PDF·HWPX·DOCX를 조항 단위로 나눠 data/parsed/articles.jsonl로 저장한다.

사용: python -m src.ingest            # data/raw 전체
      python -m src.ingest --src data/updates --out data/parsed/updates.jsonl
"""
import argparse
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from src.config import PARSED, RAW, ROOT

META_KEYS = {"문서번호": "doc_no", "보안등급": "security_level", "시행일": "effective_date", "개정차수": "revision"}
ART_RE = re.compile(r"^(제\d+조(?:의\d+)?)\((.+?)\)\s*(.*)$")
REQUIRED = ["doc", "doc_no", "article", "effective_date", "security_level", "revision"]


def read_lines(path: Path) -> list[str]:
    if path.suffix == ".pdf":
        text = "\n".join(p.extract_text() or "" for p in PdfReader(str(path)).pages)
        return [l.strip() for l in text.splitlines() if l.strip()]
    if path.suffix == ".docx":
        return [p.text.strip() for p in Document(str(path)).paragraphs if p.text.strip()]
    if path.suffix == ".hwpx":
        return read_hwpx(path)
    raise ValueError(f"지원하지 않는 형식: {path.suffix}")


def read_hwpx(path: Path) -> list[str]:
    """HWPX(한글 문서)는 zip 안의 Contents/section*.xml에 문단(<hp:p>)과 글자(<hp:t>)가 들어 있다."""
    lines = []
    with zipfile.ZipFile(path) as z:
        for name in sorted(n for n in z.namelist() if re.match(r"Contents/section\d+\.xml$", n)):
            xml = z.read(name).decode("utf-8")
            for para in re.findall(r"<hp:p\b.*?</hp:p>", xml, re.S):
                text = "".join(re.findall(r"<hp:t\b[^>]*>(.*?)</hp:t>", para, re.S))
                text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&amp;", "&").strip()
                if text:
                    lines.append(text)
    return lines


def parse_file(path: Path) -> list[dict]:
    lines = read_lines(path)
    meta = {"doc": lines[0]}
    i = 1
    while i < len(lines) and ":" in lines[i] and lines[i].split(":")[0].strip() in META_KEYS:
        k, v = lines[i].split(":", 1)
        meta[META_KEYS[k.strip()]] = v.strip()
        i += 1
    meta["revision"] = int(meta.get("revision", 1))

    articles, cur = [], None
    for line in lines[i:]:
        m = ART_RE.match(line)
        if m or line == "부칙":
            if cur:
                articles.append(cur)
            if m:
                cur = {"article": m.group(1), "title": m.group(2), "body": [m.group(3)] if m.group(3) else []}
            else:
                cur = {"article": "부칙", "title": "", "body": []}
        elif cur:
            # PDF는 한 문장이 여러 줄로 나뉜다. 항(①)이나 호(1.)로 시작하지 않으면 앞 줄에 이어 붙인다.
            if path.suffix == ".pdf" and cur["body"] and not re.match(r"^([①-⑳]|\d+\.)", line):
                cur["body"][-1] += " " + line
            else:
                cur["body"].append(line)
    if cur:
        articles.append(cur)

    rel = path.relative_to(ROOT).as_posix()
    out = []
    for a in articles:
        out.append({
            "chunk_id": f"{meta.get('doc_no')}_r{meta['revision']}_{a['article']}",
            "doc": meta["doc"], "doc_no": meta.get("doc_no"),
            "article": a["article"], "title": a["title"], "text": "\n".join(a["body"]),
            "effective_date": meta.get("effective_date"), "security_level": meta.get("security_level"),
            "revision": meta["revision"], "status": "current", "source_path": rel,
        })
    return out


def mark_status(rows: list[dict]) -> None:
    """같은 문서번호에서 가장 높은 개정차수만 current, 나머지는 superseded."""
    latest = defaultdict(int)
    for r in rows:
        latest[r["doc_no"]] = max(latest[r["doc_no"]], r["revision"])
    for r in rows:
        r["status"] = "current" if r["revision"] == latest[r["doc_no"]] else "superseded"


def ingest(src: Path, out: Path) -> list[dict]:
    rows, failed = [], []
    for path in sorted(src.rglob("*")):
        if path.suffix not in (".pdf", ".docx", ".hwpx"):
            continue
        try:
            arts = parse_file(path)
            if not arts:
                raise ValueError("조항 0개")
            rows += arts
        except Exception as e:  # noqa: BLE001
            failed.append((path.name, str(e)))
    mark_status(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    missing = sum(1 for r in rows for k in REQUIRED if not r.get(k))
    print(f"문서 {len({r['source_path'] for r in rows})}개, 조항 {len(rows)}개 → {out.relative_to(ROOT)}")
    print(f"파싱 실패 문서: {len(failed)}건 {failed if failed else ''}")
    print(f"메타데이터 누락: {missing}건")
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(RAW))
    ap.add_argument("--out", default=str(PARSED))
    a = ap.parse_args()
    ingest(Path(a.src).resolve(), Path(a.out).resolve())
