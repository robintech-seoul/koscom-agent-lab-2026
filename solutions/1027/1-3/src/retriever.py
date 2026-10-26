"""조항 검색기: BM25(공백 / Kiwi 형태소), 벡터(KURE-v2 + Chroma), RRF 결합, 선택적으로 리랭커 적용.

    from src.retriever import hybrid_search
    hybrid_search("시세 전송 지연 통보 기준", k=5, filters={"security_level": ["일반"]}, mode="hybrid")
    hybrid_search("...", k=5, mode="hybrid", rerank=True)   # 상위 20건을 리랭커로 다시 정렬

filters
    security_level : str 또는 list   — 이 등급의 조항만
    effective_date : "YYYY-MM-DD"     — 이 날짜에 이미 시행된 조항만 (시행일 <= 값)
    status         : "current"        — 현행 조항만 (개정 전·폐지 제외)
DEFAULT_FILTERS의 값이 모든 검색에 기본으로 붙는다(4-3).
"""
import json
import os
import threading
from functools import lru_cache

from src.config import CHROMA_DIR, EMBED_MODEL_DIR, PARSED, RERANK_MODEL_DIR

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
MODES = ("hybrid", "bm25", "bm25_kiwi", "vector")
RRF_K = 60
RERANK_POOL = 20   # 리랭커에 넘길 후보 수
# 4-3: update_index가 '기준일 현재 시행 중' 필터를 data/parsed/default_filters.json에 저장한다. 모든 검색에 적용
_DF_PATH = PARSED.parent / "default_filters.json"
DEFAULT_FILTERS: dict = json.loads(_DF_PATH.read_text(encoding="utf-8")) if _DF_PATH.exists() else {}
COLLECTION = "articles"
_LOCK = threading.Lock()   # 평가 러너가 여러 스레드로 돌 때 모델·DB 초기화를 한 번만


def index_text(r: dict) -> str:
    head = f"{r['doc']} {r['article']}" + (f"({r['title']})" if r.get("title") else "")
    return f"{head}\n{r['text']}"


@lru_cache(maxsize=1)
def load_articles() -> list[dict]:
    with open(PARSED, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def reload() -> None:
    """articles.jsonl이 바뀐 뒤(4-3 증분 반영) 캐시를 비운다."""
    load_articles.cache_clear()
    _bm25.cache_clear()


# ---------- BM25 ----------
@lru_cache(maxsize=1)
def _kiwi():
    from kiwipiepy import Kiwi
    return Kiwi()


def tok_space(text: str) -> list[str]:
    return text.split()


def tok_kiwi(text: str) -> list[str]:
    keep = ("NN", "NR", "NP", "VV", "VA", "XR", "SL", "SN", "SH", "MM")
    return [t.form for t in _kiwi().tokenize(text) if t.tag.startswith(keep)]


@lru_cache(maxsize=2)
def _bm25(kind: str):
    from rank_bm25 import BM25Okapi
    tok = tok_kiwi if kind == "kiwi" else tok_space
    return BM25Okapi([tok(index_text(r)) for r in load_articles()]), tok


def bm25_rank(query: str, kind: str = "space") -> list[int]:
    with _LOCK:
        bm, tok = _bm25(kind)
    scores = bm.get_scores(tok(query))
    return sorted(range(len(scores)), key=lambda i: -scores[i])


# ---------- 벡터 ----------
@lru_cache(maxsize=1)
def _embedder():
    import torch
    from sentence_transformers import SentenceTransformer
    # KURE-v2는 원래 토큰별 벡터(ColBERT) 모델이다. sentence-transformers가 문장당 벡터 1개로 바꿔 불러온다.
    # CPU에서는 float32가 bfloat16보다 훨씬 빠르다. 조항은 512토큰이면 충분하다.
    m = SentenceTransformer(str(EMBED_MODEL_DIR), device="cpu", model_kwargs={"dtype": torch.float32})
    m.max_seq_length = 512
    return m


def embed(texts: list[str]) -> list[list[float]]:
    return _embedder().encode(texts, batch_size=16, normalize_embeddings=True, show_progress_bar=False).tolist()


@lru_cache(maxsize=1)
def _client():
    import chromadb
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def _collection():
    return _client().get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})


def build_index(rows: list[dict] | None = None, rebuild: bool = False) -> int:
    """articles.jsonl을 Chroma에 넣는다. 이미 있는 chunk_id는 건너뛴다."""
    rows = rows if rows is not None else load_articles()
    if rebuild:
        client = _client()
        if COLLECTION in [c.name for c in client.list_collections()]:
            client.delete_collection(COLLECTION)
    col = _collection()
    have = set(col.get(ids=[r["chunk_id"] for r in rows])["ids"]) if rows else set()
    new = [r for r in rows if r["chunk_id"] not in have]
    for s in range(0, len(new), 64):
        batch = new[s:s + 64]
        col.add(ids=[r["chunk_id"] for r in batch], embeddings=embed([index_text(r) for r in batch]),
                documents=[index_text(r) for r in batch],
                metadatas=[{k: r[k] for k in ("doc", "article", "effective_date", "security_level", "status")}
                           | {"revision": r["revision"]} for r in batch])
    return len(new)


def vector_rank(query: str, n: int) -> list[int]:
    with _LOCK:
        col = _collection()
        if col.count() == 0:
            build_index()
        qv = embed([query])
        res = col.query(query_embeddings=qv, n_results=min(n, col.count()))
    pos = {r["chunk_id"]: i for i, r in enumerate(load_articles())}
    return [pos[i] for i in res["ids"][0] if i in pos]


# ---------- 리랭커 ----------
@lru_cache(maxsize=1)
def _reranker():
    from sentence_transformers import CrossEncoder
    # 질문과 조항을 한 쌍으로 넣어 관련도를 다시 매기는 모델(cross-encoder). 실습 PC에 미리 받아 둔 폴더에서 읽는다.
    return CrossEncoder(str(RERANK_MODEL_DIR), device="cpu", max_length=512)


def rerank(query: str, rows: list[dict]) -> list[dict]:
    with _LOCK:
        model = _reranker()
    scores = model.predict([(query, index_text(r)) for r in rows], batch_size=8, show_progress_bar=False)
    return [r for _, r in sorted(zip(scores, rows), key=lambda x: -x[0])]


# ---------- 필터와 결합 ----------
def passes(r: dict, filters: dict | None) -> bool:
    if not filters:
        return True
    lv = filters.get("security_level")
    if lv and r["security_level"] not in ([lv] if isinstance(lv, str) else lv):
        return False
    if filters.get("effective_date") and r["effective_date"] > filters["effective_date"]:
        return False
    if filters.get("status") and r.get("status") != filters["status"]:
        return False
    return True


def rrf(rankings: list[list[int]]) -> list[int]:
    score: dict[int, float] = {}
    for ranking in rankings:
        for rank, i in enumerate(ranking):
            score[i] = score.get(i, 0.0) + 1.0 / (RRF_K + rank + 1)
    return sorted(score, key=lambda i: -score[i])


def hybrid_search(query: str, k: int = 5, filters: dict | None = None, mode: str = "hybrid",
                  rerank_on: bool = False) -> list[dict]:
    if mode not in MODES:
        raise ValueError(f"mode는 {MODES} 중 하나")
    filters = {**DEFAULT_FILTERS, **(filters or {})} or None
    arts = load_articles()
    pool = len(arts)
    if mode == "bm25":
        order = bm25_rank(query, "space")
    elif mode == "bm25_kiwi":
        order = bm25_rank(query, "kiwi")
    elif mode == "vector":
        order = vector_rank(query, pool)
    else:
        order = rrf([bm25_rank(query, "kiwi")[:50], vector_rank(query, 50)])
    want = max(k, RERANK_POOL) if rerank_on else k
    out = []
    for i in order:
        if passes(arts[i], filters):
            out.append(arts[i])
        if len(out) == want:
            break
    return rerank(query, out)[:k] if rerank_on else out


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--build"]:
        print("새로 넣은 조항:", build_index(rebuild=True))
    else:
        for r in hybrid_search(" ".join(sys.argv[1:]) or "시세 전송 지연 통보 기준"):
            print(r["doc"], r["article"], r["effective_date"], r["status"])
