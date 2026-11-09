"""Golden-set evaluation harness for the API sample and synthetic payment fixture."""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Literal

from app.ai.classifier import classify
from app.ai.fallback import rules_classify

GOLDEN_PATH = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "golden_eval_100.json"
SYNTHETIC_PAYMENT_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "golden_classification_synthetic.jsonl"


def load_golden_set(path: Path | None = None) -> list[dict]:
    target = path or GOLDEN_PATH
    if not target.exists():
        raise FileNotFoundError(f"Golden evaluation set not found at {target}")
    return json.loads(target.read_text(encoding="utf-8"))


def evaluate_golden_set(mode: Literal["rules", "auto"] = "rules", path: Path | None = None) -> dict:
    """Evaluate classifier accuracy, per-language accuracy, fraud recall, and confusion matrix."""
    items = load_golden_set(path)
    total = len(items)
    issue_correct = 0
    lang_correct = 0
    fraud_tp = fraud_fp = fraud_fn = 0

    by_lang_total: dict[str, int] = defaultdict(int)
    by_lang_correct: dict[str, int] = defaultdict(int)
    by_issue_total: dict[str, int] = defaultdict(int)
    by_issue_correct: dict[str, int] = defaultdict(int)
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for item in items:
        text = item["text"]
        channel = item.get("channel", "unknown")
        expected_issue = item["issue_type"]
        expected_lang = item["language"]
        expected_fraud = bool(item.get("is_fraud", expected_issue == "fraud_scam"))

        if mode == "auto":
            pred, _ = classify(text, channel)
        else:
            pred = rules_classify(text)

        pred_issue = pred.issue_type.value if hasattr(pred.issue_type, "value") else pred.issue_type
        pred_lang = pred.language
        pred_fraud = bool(pred.is_fraud)

        by_lang_total[expected_lang] += 1
        by_issue_total[expected_issue] += 1
        confusion[expected_issue][pred_issue] += 1

        if pred_issue == expected_issue:
            issue_correct += 1
            by_lang_correct[expected_lang] += 1
            by_issue_correct[expected_issue] += 1
        if pred_lang == expected_lang:
            lang_correct += 1

        if expected_fraud and pred_fraud:
            fraud_tp += 1
        elif not expected_fraud and pred_fraud:
            fraud_fp += 1
        elif expected_fraud and not pred_fraud:
            fraud_fn += 1

    return {
        "total": total,
        "mode": mode,
        "overall_accuracy": round(issue_correct / max(total, 1), 4),
        "language_detection_accuracy": round(lang_correct / max(total, 1), 4),
        "fraud_precision": round(fraud_tp / max(fraud_tp + fraud_fp, 1), 4),
        "fraud_recall": round(fraud_tp / max(fraud_tp + fraud_fn, 1), 4),
        "accuracy_by_language": {
            lang: round(by_lang_correct[lang] / count, 4) for lang, count in sorted(by_lang_total.items())
        },
        "accuracy_by_issue_type": {
            issue: round(by_issue_correct[issue] / count, 4) for issue, count in sorted(by_issue_total.items())
        },
        "confusion_matrix": {
            actual: dict(sorted(preds.items())) for actual, preds in sorted(confusion.items())
        },
    }


def evaluate_synthetic_payment_set(
    *, live: bool = False, path: Path | None = None
) -> dict:
    """Evaluate the labeled synthetic fixture; live mode uses the configured provider."""
    target = path or SYNTHETIC_PAYMENT_PATH
    if not target.exists():
        raise FileNotFoundError(f"Synthetic payment fixture not found at {target}")
    rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
    by_group: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    correct_confidence = []
    incorrect_confidence = []
    sources: dict[str, int] = defaultdict(int)
    for row in rows:
        if live:
            result, source = classify(row["text"], row.get("channel", "unknown"))
            sources[source] += 1
        else:
            result = rules_classify(row["text"])
            sources["rules"] += 1
        correct = result.payment_category == row["gold_payment_category"]
        counts = by_group[row["group"]]
        counts[1] += 1
        if correct:
            counts[0] += 1
            correct_confidence.append(result.confidence)
        else:
            incorrect_confidence.append(result.confidence)

    total = len(rows)
    correct_total = sum(values[0] for values in by_group.values())
    return {
        "mode": "live" if live else "rules",
        "total": total,
        "overall_accuracy": round(correct_total / total, 4) if total else 0.0,
        "accuracy_by_group": {
            group: round(correct / count, 4) for group, (correct, count) in sorted(by_group.items())
        },
        "average_confidence_when_correct": (
            round(sum(correct_confidence) / len(correct_confidence), 4) if correct_confidence else None
        ),
        "average_confidence_when_incorrect": (
            round(sum(incorrect_confidence) / len(incorrect_confidence), 4)
            if incorrect_confidence else None
        ),
        "sources": dict(sorted(sources.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the synthetic payment classification fixture.")
    parser.add_argument("--live", action="store_true", help="Use the configured AI provider instead of rules.")
    args = parser.parse_args()
    result = evaluate_synthetic_payment_set(live=args.live)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
