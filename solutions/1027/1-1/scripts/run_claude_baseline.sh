#!/usr/bin/env bash
# 기준선(통째 넣기, 1-1): eval/questions.jsonl의 각 질문에 대해 claude -p(헤드리스)를 호출한다.
# - 도구는 Read만 허용, 읽을 파일은 data/regs_all.md 하나
# - --output-format json 결과에서 답변·토큰·비용을 추출해 eval/results/baseline_r<회차>.jsonl로 저장 (CLAUDE.md 3절 형식)
# - --model은 CLAUDE.md의 고정 모델
#
# 사용: bash scripts/run_claude_baseline.sh [회차=1] [질문파일=eval/questions.jsonl]
#       Windows는 Git Bash에서 실행한다. 동시 실행 수는 WORKERS(기본 4)로 바꾼다.
#       질문 파일, data/, eval/results/는 저장소 루트(이 수업 폴더의 ../..) 기준이다. claude도 루트에서 실행한다.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"            # 이 스크립트가 있는 scripts/
ROOT="$(cd "$HERE/../../.." && pwd)"             # 저장소 루트 (data/, eval/, CLAUDE.md)
cd "$ROOT"

RUN="${1:-1}"
QFILE="${2:-eval/questions.jsonl}"
WORKERS="${WORKERS:-4}"
METHOD="${METHOD:-baseline}"
MODEL="claude-haiku-5-5"                            # CLAUDE.md 2절 고정 모델 (Claude 구독 계정)
TOOLS="${TOOLS_OVERRIDE:-Read}"
PROMPT_HEAD='data/regs_all.md 전체를 읽고, 그 내용만 근거로 다음 질문에 답해줘.
다른 파일은 열지 마. 답에는 문서명·조항·시행일을 「문서명」 제N조(시행일 YYYY-MM-DD) 형식으로 인용해.
근거가 없으면 '"'문서에 없음'"'이라고 답해.'
PROMPT_HEAD="${PROMPT_HEAD_OVERRIDE:-$PROMPT_HEAD}"
OUT="eval/results/${METHOD}_r${RUN}.jsonl"
PY="${PYTHON:-python}"

# Claude Code는 로그인한 Claude 구독 계정으로만 실행한다. API 키(BizRouter 등)로 실행하지 않는다.
unset ANTHROPIC_API_KEY ANTHROPIC_BASE_URL

TMP=$(mktemp -d)
N=$($PY -c "import sys; print(sum(1 for l in open(sys.argv[1], encoding='utf-8') if l.strip()))" "$QFILE")
echo "${METHOD} ${RUN}회차: ${N}건, 동시 ${WORKERS}개"

run_one() {   # $1 = 질문 순번(0부터)
  local i=$1 q t0 t1
  q=$($PY -c "import json,sys; qs=[json.loads(l) for l in open(sys.argv[1], encoding='utf-8') if l.strip()]; print(qs[int(sys.argv[2])]['question'])" "$QFILE" "$i")
  t0=$($PY -c "import time; print(time.time())")
  # 프롬프트는 표준 입력으로 넘긴다 (Windows에서 여러 줄 인자가 깨지지 않게)
  printf '%s\n질문: %s\n' "$PROMPT_HEAD" "$q" \
    | claude -p --model "$MODEL" --output-format json --allowedTools $TOOLS --setting-sources project \
    > "$TMP/$i.json" 2> "$TMP/$i.err" || true
  t1=$($PY -c "import time; print(time.time())")
  $PY "$HERE/claude_result.py" "$QFILE" "$i" "$TMP/$i.json" "$t0" "$t1" "$METHOD" > "$TMP/$i.line"
  echo "  $((i + 1))/${N} 완료"
}

for ((i = 0; i < N; i++)); do
  run_one "$i" &
  while (( $(jobs -rp | wc -l) >= WORKERS )); do sleep 1; done
done
wait

mkdir -p eval/results
: > "$OUT"
for ((i = 0; i < N; i++)); do cat "$TMP/$i.line" >> "$OUT"; done
rm -rf "$TMP"
echo "${N}건 → ${OUT} (오류 $(grep -c '"error"' "$OUT" || true)건)"
