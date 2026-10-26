"""2-1 실습 ②-2: 사람 채점(eval/human_labels.csv)과 RAGAS 점수 비교표

python -m src.compare_human [--results eval/results/rag_r1.jsonl]
RAGAS 점수는 eval/results/scores.csv(run_eval --score 결과)에서 가장 최근 값을 쓴다.
"""
import argparse
import csv

from src.config import EVAL, RESULTS


def latest_scores(result_name: str) -> dict:
    out = {}
    path = RESULTS / "scores.csv"
    if not path.exists():
        return out
    for row in csv.DictReader(open(path, encoding="utf-8")):
        if row["result"] == result_name and row["id"] != "_mean":
            out.setdefault(row["id"], {})[row["metric"]] = row["value"]
    return out


def main():
    labels = list(csv.DictReader(open(EVAL / "human_labels.csv", encoding="utf-8")))
    cache = {}
    print("| id | 사람: 정답 | 사람: 근거 일치 | RAGAS faithfulness | RAGAS context_recall | 불일치 | 메모 |")
    print("|---|---|---|---|---|---|---|")
    for lb in labels:
        s = cache.setdefault(lb["result_file"], latest_scores(lb["result_file"])).get(lb["id"], {})
        f = s.get("faithfulness", "")
        mismatch = f and ((float(f) >= 0.8) != (lb["human_correct"] == "1"))
        print(f"| {lb['id']} | {lb['human_correct']} | {lb['human_faithful']} | {f} | {s.get('context_recall', '')} | "
              f"{'⚠' if mismatch else ''} | {lb['note']} |")
    print("\n불일치(⚠): RAGAS faithfulness가 0.8 이상인데 사람은 오답, 또는 그 반대")


if __name__ == "__main__":
    argparse.ArgumentParser().parse_args()
    main()
