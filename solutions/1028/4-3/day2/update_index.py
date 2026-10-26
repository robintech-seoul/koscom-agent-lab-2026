"""문서 개정 반영 (4-3): data/updates/의 신규·개정·폐지 문서를 증분 반영한다.

- 신규: 조항 추가
- 개정: 새 판 추가, 같은 문서번호의 이전 판 조항은 status=superseded
- 폐지: 폐지 공고가 가리키는 문서번호(repeals)의 조항은 삭제
- hybrid_search 기본 필터를 '기준일 현재 시행 중'으로 (src.retriever.DEFAULT_FILTERS)

python -m day2.update_index [--as-of 2026-10-27]
"""
import argparse
import json
import re

from src import retriever
from src.config import PARSED, UPDATES
from src.ingest import mark_status, parse_file

REPEAL_RE = re.compile(r"\(?(HB-[A-Z]+-\d{3})\)?[^\n]*폐지")


def current_filter(as_of: str) -> dict:
    return {"effective_date": as_of, "status": "current"}


def apply_updates(as_of: str) -> dict:
    rows = [json.loads(l) for l in open(PARSED, encoding="utf-8")]
    have = {r["chunk_id"] for r in rows}
    added, repealed = [], set()
    for path in sorted(UPDATES.rglob("*")):
        if path.suffix not in (".pdf", ".docx"):
            continue
        arts = parse_file(path)
        body = " ".join(a["text"] for a in arts)
        m = REPEAL_RE.search(body)
        if m and "폐지" in arts[0]["doc"]:
            repealed.add(m.group(1))          # 폐지 공고 자체도 근거로 남긴다
        added += [a for a in arts if a["chunk_id"] not in have]
    before = len(rows)
    rows = [r for r in rows if r["doc_no"] not in repealed] + added
    mark_status(rows)
    PARSED.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")

    # 벡터 색인: 폐지 조항 삭제, 새 조항 추가, status 메타데이터 갱신
    col = retriever._collection()
    gone = [i for i in col.get()["ids"] if i not in {r["chunk_id"] for r in rows}]
    if gone:
        col.delete(ids=gone)
    retriever.reload()
    n_new = retriever.build_index(added)
    for r in rows:
        col.update(ids=[r["chunk_id"]], metadatas=[{"status": r["status"]}]) if r["status"] == "superseded" else None
    retriever.DEFAULT_FILTERS.update(current_filter(as_of))
    retriever._DF_PATH.write_text(json.dumps(retriever.DEFAULT_FILTERS, ensure_ascii=False), encoding="utf-8")   # 다음 실행에도 적용
    stats = {"before": before, "after": len(rows), "added": len(added), "indexed": n_new,
             "deleted": len(gone), "repealed_docs": sorted(repealed),
             "superseded": sum(r["status"] == "superseded" for r in rows)}
    print(json.dumps(stats, ensure_ascii=False))
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default="2026-10-27")
    apply_updates(ap.parse_args().as_of)
