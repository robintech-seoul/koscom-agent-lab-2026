"""에이전트가 쓰는 공통 도구: grep, read_file, hybrid_search(검색), read_source(조항 원문)

권한(4-2): 도구는 현재 사용자 역할(role)을 contextvar에서 읽어, 그 역할이 볼 수 있는 폴더·등급만 허용한다.
1일차에는 role이 설정되지 않으므로 기본값 'admin'(전체 허용)으로 동작한다.
"""
import contextvars
import json
import re
from pathlib import Path

from langchain_core.tools import tool

from src.config import LEVEL_DIR, RAW, ROLE_LEVELS, ROOT
from src.retriever import hybrid_search as _search
from src.retriever import load_articles

CURRENT_ROLE: contextvars.ContextVar[str] = contextvars.ContextVar("role", default="admin")
MAX_CHARS = 6000
OUTPUT_FILTERS: list = []           # 4-2: 도구 결과를 모델에 넘기기 전에 거치는 함수들 (text -> text)


def filter_output(text: str) -> str:
    for f in OUTPUT_FILTERS:
        text = f(text)
    return text


def allowed_dirs(role: str) -> list[Path]:
    return [RAW / LEVEL_DIR[lv] for lv in ROLE_LEVELS.get(role, ["일반"])]


def _check_path(path: str) -> Path:
    p = (ROOT / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    dirs = allowed_dirs(CURRENT_ROLE.get())
    if not any(p == d or d in p.parents for d in dirs):
        raise PermissionError(f"접근 권한 없음: {path} (역할 {CURRENT_ROLE.get()})")
    return p


def _read_text(p: Path) -> str:
    if p.suffix == ".pdf":
        from pypdf import PdfReader
        return "\n".join(pg.extract_text() or "" for pg in PdfReader(str(p)).pages)
    if p.suffix == ".docx":
        from docx import Document
        return "\n".join(par.text for par in Document(str(p)).paragraphs)
    if p.suffix == ".hwpx":
        from src.ingest import read_hwpx
        return "\n".join(read_hwpx(p))
    return p.read_text(encoding="utf-8")


@tool
def grep(pattern: str, path: str = "data/raw") -> str:
    """원문 폴더에서 정규식 pattern이 나오는 줄을 찾는다. PDF·HWPX·DOCX도 텍스트로 읽어 검색한다.
    결과: '파일경로:줄번호: 내용' 목록 (최대 40줄)."""
    try:
        base = _check_path(path) if path not in ("data/raw", "") else None
    except PermissionError as e:
        return str(e)
    roots = [base] if base else allowed_dirs(CURRENT_ROLE.get())
    rx = re.compile(pattern)
    hits = []
    for root in roots:
        files = [root] if root.is_file() else sorted(root.rglob("*"))
        for f in files:
            if f.suffix not in (".pdf", ".docx", ".hwpx", ".md"):   # .txt는 Claude Code용 사본이라 건너뛴다
                continue
            for i, line in enumerate(_read_text(f).splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{f.relative_to(ROOT)}:{i}: {line.strip()[:200]}")
    return filter_output("\n".join(hits[:40]) or "결과 없음")


@tool
def read_file(path: str) -> str:
    """원문 파일 하나를 텍스트로 읽는다. path 예: data/raw/public/시세정보전송규정_2026-03-01.pdf"""
    try:
        text = _read_text(_check_path(path))
    except (PermissionError, FileNotFoundError) as e:
        return str(e)
    return filter_output(text[:MAX_CHARS] + ("\n...(이하 생략)" if len(text) > MAX_CHARS else ""))


@tool
def hybrid_search(query: str, k: int = 5, filters: dict | None = None) -> str:
    """사내 규정 조항을 하이브리드 검색(BM25 + 벡터)으로 찾는다. 결과는 조항 목록(JSON).
    filters 예: {"effective_date": "2026-10-27"}"""
    f = dict(filters or {})
    f["security_level"] = ROLE_LEVELS.get(CURRENT_ROLE.get(), ["일반"])
    rows = _search(query, k=k, filters=f)
    return filter_output(json.dumps([{k_: r[k_] for k_ in ("doc", "article", "title", "effective_date",
                                                             "security_level", "text")} for r in rows], ensure_ascii=False))


def source_lookup(doc: str, article: str, effective_date: str | None = None) -> dict | None:
    """조항 원문 레코드를 찾는다. 시행일이 없으면 가장 최근 판."""
    cands = [r for r in load_articles() if r["doc"] == doc.replace(" ", "") and r["article"] == article
             and r["security_level"] in ROLE_LEVELS.get(CURRENT_ROLE.get(), ["일반"])]
    if effective_date:
        cands = [r for r in cands if r["effective_date"] == effective_date] or cands
    return max(cands, key=lambda r: r["effective_date"]) if cands else None


@tool
def read_source(doc: str, article: str) -> str:
    """규정 원문에서 조항 하나를 그대로 읽는다. 같은 조항의 여러 판이 있으면 모두 시행일과 함께 보여 준다.
    doc 예: 시세정보전송규정, article 예: 제12조"""
    lv = ROLE_LEVELS.get(CURRENT_ROLE.get(), ["일반"])
    rows = [r for r in load_articles() if r["doc"] == doc.replace(" ", "") and r["article"] == article]
    if not rows:
        return f"조항 없음: {doc} {article}"
    rows = [r for r in rows if r["security_level"] in lv]
    if not rows:
        return f"접근 권한 없음: {doc} (역할 {CURRENT_ROLE.get()})"
    return filter_output("\n\n".join(f"[{r['doc']} {r['article']}({r['title']}) | 시행일 {r['effective_date']} | "
                       f"{'현행' if r['status'] == 'current' else '개정 전'}]\n{r['text']}"
                       for r in sorted(rows, key=lambda r: r["effective_date"], reverse=True)))
