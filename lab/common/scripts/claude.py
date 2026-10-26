"""Claude Code를 고정 모델로 실행한다 (Windows·Mac 공통). 로그인한 Claude 구독 계정으로만 실행한다(API 키 사용 안 함).

수업 폴더(예: 1027/1-3)에서:
python ../../common/scripts/claude.py              # 대화형. 저장소 루트를 --add-dir로 붙여 연다
python ../../common/scripts/claude.py -p "질문"     # 그 밖의 인자는 claude에 그대로 넘긴다
"""
import subprocess
import sys

from claude_headless import CLAUDE_MODEL, ROOT, claude_env, claude_exe

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--model" not in args:
        args = ["--model", CLAUDE_MODEL, *args]
    if "--add-dir" not in args:
        args = ["--add-dir", str(ROOT), *args]   # 수업 폴더에서 열어도 루트의 data/, eval/을 읽을 수 있게
    sys.exit(subprocess.call([claude_exe(), *args], env=claude_env()))
