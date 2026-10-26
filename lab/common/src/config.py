"""공통 설정: 경로, 모델, 단가, LLM과 임베딩 생성 함수."""
import os
from pathlib import Path

from dotenv import load_dotenv

# 저장소 루트 (solutions/ 또는 lab/). 데이터, 평가셋, .env, models/, 결과는 모두 루트에 있고 모든 수업이 함께 쓴다.
ROOT = Path(__file__).resolve().parents[2]
COMMON = ROOT / "common"
load_dotenv(ROOT / ".env")

DATA = ROOT / "data"
RAW = DATA / "raw"
PARSED = DATA / "parsed" / "articles.jsonl"
UPDATES = DATA / "updates"
EVAL = ROOT / "eval"
RESULTS = EVAL / "results"
WIKI = ROOT / "wiki"                       # 과제 1에서 만드는 위키
PREBUILT_WIKI = DATA / "wiki"              # 미리 만든 위키
PREBUILT_WIKI_UPDATED = DATA / "wiki_updated"
DART_CACHE = DATA / "dart_cache"
COMPANIES = DATA / "companies.json"
LOGS = ROOT / "logs"
CHROMA_DIR = ROOT / ".chroma"
EMBED_MODEL_DIR = ROOT / "models" / "KURE-v2"
RERANK_MODEL_DIR = ROOT / "models" / os.environ.get("RERANK_MODEL", "mmarco-mMiniLMv2")   # 1-3 리랭커 (선택)

MODEL = "anthropic/claude-haiku-5.5"
BASE_URL = "https://api.bizrouter.ai"
# USD / 100만 토큰 (BizRouter Haiku 5.5, 2026-10-26 실측. 캐시 단가는 입력 단가의 0.1배·1.25배로 계산)
PRICE = {"input": 0.1, "output": 0.5, "cache_read": 0.01, "cache_write": 0.125}

# 역할별로 읽을 수 있는 보안 등급과 원문 폴더
ROLE_LEVELS = {
    "general": ["일반"],
    "staff": ["일반", "대외비"],
    "admin": ["일반", "대외비", "비밀"],
}
LEVEL_DIR = {"일반": "public", "대외비": "internal", "비밀": "secret"}



def root_path(p) -> Path:
    """명령줄에 준 상대 경로(eval/sets/..., eval/results/...)는 지금 폴더에 없으면 저장소 루트 기준으로 찾는다."""
    p = Path(p)
    return p if p.is_absolute() or p.exists() else ROOT / p


def get_llm(max_tokens: int = 4000, temperature: float = 0.0):
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=MODEL,
        base_url=BASE_URL,
        api_key=os.environ["BIZROUTER_API_KEY"],
        max_tokens=max_tokens,
        temperature=temperature,
        max_retries=10,      # 호출 한도(429)·일시 연결 오류는 기다렸다 다시 시도한다 (여럿이 동시에 실습할 때 필요)
    )


def cost_usd(input_tokens: int, output_tokens: int, cache_read: int = 0, cache_write: int = 0) -> float:
    """input_tokens에는 캐시 토큰이 포함되지 않은 값(LangChain usage_metadata 기준은 포함)을 넣는다."""
    return round(
        (input_tokens * PRICE["input"] + output_tokens * PRICE["output"]
         + cache_read * PRICE["cache_read"] + cache_write * PRICE["cache_write"]) / 1_000_000,
        6,
    )


def usage_from_callback(usage_metadata: dict) -> dict:
    """get_usage_metadata_callback() 결과를 입력/출력 토큰과 비용으로 바꾼다."""
    inp = out = cr = cw = 0
    for u in usage_metadata.values():
        d = u.get("input_token_details", {}) or {}
        cr += d.get("cache_read", 0) or 0
        cw += d.get("cache_creation", 0) or 0
        inp += u.get("input_tokens", 0)
        out += u.get("output_tokens", 0)
    plain = max(inp - cr - cw, 0)
    return {"input_tokens": inp, "output_tokens": out, "cost_usd": cost_usd(plain, out, cr, cw)}
