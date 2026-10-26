#!/usr/bin/env bash
# (선택, 2-3) 직접 탐색: run_claude_baseline.sh와 같은 방식. 허용 도구는 Read, Grep, Glob. 대상은 data/raw/.
# data/raw/의 각 원문 옆에 텍스트 사본(.txt)이 있어 Grep으로 찾을 수 있다 (scripts/make_raw_text.py로 생성).
# 결과는 eval/results/explore_r<회차>.jsonl
#
# 사용: bash scripts/run_claude_explore.sh [회차=1] [질문파일=eval/questions.jsonl]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"    # 저장소 루트
export METHOD=explore
export PROMPT_HEAD_OVERRIDE='data/raw/ 폴더만 사용해서 답해줘. 색인이나 data/parsed, data/regs_all.md는 쓰지 마.
답에는 「문서명」 제N조(시행일 YYYY-MM-DD) 형식으로 인용해.'
TOOLS_OVERRIDE="Read Grep Glob" exec bash "$ROOT/1027/1-1/scripts/run_claude_baseline.sh" "$@"   # 1-1에서 만든 스크립트를 그대로 쓴다
