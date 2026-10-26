"""헤드리스 셸 스크립트(run_claude_*.sh)용: claude -p 의 JSON 출력 1건을 결과 파일 한 줄(CLAUDE.md 3절 형식)로 바꾼다.

python scripts/claude_result.py <질문파일> <순번> <claude 출력 json> <시작 시각> <끝 시각> <method>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "common" / "scripts"))   # claude_headless.py
from claude_headless import to_result  # noqa: E402

qfile, idx, out_json, t0, t1, method = sys.argv[1:7]
qs = [json.loads(l) for l in open(qfile, encoding="utf-8") if l.strip()]
raw = Path(out_json).read_text(encoding="utf-8", errors="ignore")
try:
    d = json.loads(raw[raw.index("{"):])
except ValueError:
    d = {"is_error": True, "result": raw[:500] or "claude 출력 없음"}
row = to_result(qs[int(idx)], d, float(t1) - float(t0), method)
print(json.dumps(row, ensure_ascii=False))
