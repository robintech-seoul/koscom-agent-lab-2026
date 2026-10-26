"""OpenDART 공시 조회 MCP 서버 (stdio). dart_cli.py와 같은 함수를 MCP 도구로 내보낸다.

실행 확인: python day2/dart_mcp.py   (stdio로 MCP 클라이언트를 기다린다)
Claude Desktop 연결: claude_desktop_config.json의 mcpServers에 command/args로 등록 (README 참고)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp.server.fastmcp import FastMCP  # noqa: E402

import dart_cli  # noqa: E402

mcp = FastMCP("dart", log_level="WARNING")


@mcp.tool()
def search_disclosures(corp: str, days: int = 90) -> dict:
    """회사의 최근 공시 목록을 조회한다.

    Args:
        corp: 회사. 'A사', 'B사', 회사명 또는 DART corp_code(8자리 숫자)
        days: 오늘부터 며칠 전까지 조회할지 (1~365, 기본 90)
    Returns:
        list: 공시 목록. 각 항목의 report_nm=공시 제목, rcept_no=접수번호(14자리), rcept_dt=제출일(YYYYMMDD)
    """
    return dart_cli.search(corp, max(1, min(days, 365)))


@mcp.tool()
def get_disclosure_document(rcept_no: str) -> dict:
    """공시 원문 텍스트의 앞부분을 가져온다.

    Args:
        rcept_no: 접수번호 14자리 숫자 (search_disclosures 결과의 rcept_no)
    """
    return dart_cli.document(rcept_no)


if __name__ == "__main__":
    mcp.run()   # stdio
