"""OpenDART 공시 조회 CLI (3-1). 결과는 JSON으로 stdout에 출력한다.

  python day2/dart_cli.py search --corp A사 --days 90
  python day2/dart_cli.py document --rcept-no 20261015000123

- 키: 환경 변수 DART_API_KEY (.env)
- 키가 없거나 DART_MOCK=1이면 solutions/dart_cache/의 녹화 응답(mock)을 쓴다.
- 가상 회사(A사, B사, corp_code 99로 시작)와 그 공시는 키가 있어도 항상 녹화 응답을 쓴다.
"""
import argparse
import io
import json
import os
import re
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path

from src.config import COMPANIES as COMPANIES_PATH, DART_CACHE, ROOT  # noqa: E402  (.env도 여기서 읽힌다)

API = "https://opendart.fss.or.kr/api"
CACHE = DART_CACHE
COMPANIES = json.loads(COMPANIES_PATH.read_text(encoding="utf-8"))
MOCK_TODAY = date(2026, 10, 27)


def use_mock() -> bool:
    return os.environ.get("DART_MOCK") == "1" or not os.environ.get("DART_API_KEY")


def is_fictional(corp_code: str) -> bool:
    return corp_code.startswith("99")


def resolve_corp(corp: str) -> dict:
    """'A사', 회사명, corp_code(8자리) 중 무엇이든 받아 {corp_name, corp_code}로 바꾼다."""
    if corp in COMPANIES:
        return COMPANIES[corp]
    for v in COMPANIES.values():
        if isinstance(v, dict) and corp in (v["corp_name"], v["corp_code"], v["corp_name"].replace("(가상)", "")):
            return v
    if re.fullmatch(r"\d{8}", corp):
        return {"corp_name": corp, "corp_code": corp}
    raise ValueError(f"알 수 없는 회사: {corp}. day2/companies.json에 추가하라")


def search(corp: str, days: int = 90) -> dict:
    """회사의 최근 days일 공시 목록. 각 항목: report_nm(제목), rcept_no(접수번호), rcept_dt(제출일)"""
    c = resolve_corp(corp)
    if use_mock() or is_fictional(c["corp_code"]):
        rows = json.loads((CACHE / f"list_{c['corp_code']}.json").read_text(encoding="utf-8"))
        since = (MOCK_TODAY - timedelta(days=days)).strftime("%Y%m%d")
        rows = [r for r in rows if r["rcept_dt"] >= since]
        return {"source": "mock", "as_of": MOCK_TODAY.isoformat(), "corp_name": c["corp_name"], "list": rows}
    import httpx
    end = date.today()
    params = {"crtfc_key": os.environ["DART_API_KEY"], "corp_code": c["corp_code"],
              "bgn_de": (end - timedelta(days=days)).strftime("%Y%m%d"), "end_de": end.strftime("%Y%m%d"),
              "page_count": 100}
    d = httpx.get(f"{API}/list.json", params=params, timeout=30).json()
    if d.get("status") not in ("000", "013"):           # 013 = 조회된 데이터 없음
        raise RuntimeError(f"DART 오류 {d.get('status')}: {d.get('message')}")
    keep = ("corp_name", "report_nm", "rcept_no", "rcept_dt", "flr_nm")
    return {"source": "dart", "as_of": end.isoformat(), "corp_name": c["corp_name"],
            "list": [{k: r[k] for k in keep} for r in d.get("list", [])]}


def document(rcept_no: str, max_chars: int = 4000) -> dict:
    """공시 원문 텍스트(앞부분 max_chars자)."""
    p = CACHE / f"document_{rcept_no}.txt"
    if use_mock() or p.exists():
        if not p.exists():
            raise FileNotFoundError(f"녹화 응답 없음: {rcept_no}")
        return {"source": "mock", "rcept_no": rcept_no, "text": p.read_text(encoding="utf-8")[:max_chars]}
    import httpx
    r = httpx.get(f"{API}/document.xml", params={"crtfc_key": os.environ["DART_API_KEY"], "rcept_no": rcept_no},
                  timeout=60)
    try:
        z = zipfile.ZipFile(io.BytesIO(r.content))
    except zipfile.BadZipFile:
        raise RuntimeError(f"DART 오류: {r.text[:200]}")
    xml = z.read(z.namelist()[0]).decode("utf-8", errors="ignore")
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml)).strip()
    return {"source": "dart", "rcept_no": rcept_no, "text": text[:max_chars]}


def main():
    ap = argparse.ArgumentParser(description="OpenDART 공시 조회")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search", help="회사의 최근 공시 목록")
    s.add_argument("--corp", required=True, help="A사, B사, 회사명 또는 corp_code")
    s.add_argument("--days", type=int, default=90, help="최근 며칠 (기본 90)")
    d = sub.add_parser("document", help="공시 원문 텍스트")
    d.add_argument("--rcept-no", required=True, help="접수번호 14자리")
    a = ap.parse_args()
    try:
        out = search(a.corp, a.days) if a.cmd == "search" else document(a.rcept_no)
    except Exception as e:  # noqa: BLE001
        out = {"error": f"{type(e).__name__}: {e}"}
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
