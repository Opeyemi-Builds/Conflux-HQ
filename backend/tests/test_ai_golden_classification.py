import json
from collections import defaultdict
from pathlib import Path

from app.ai.fallback import rules_classify

FIXTURE = Path(__file__).parent / "fixtures" / "golden_classification_synthetic.jsonl"


def load_fixture():
    return [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines()]


def test_synthetic_golden_classification_baseline_and_confidence(capsys):
    rows = load_fixture()
    assert len(rows) == 80
    assert {group: sum(row["group"] == group for row in rows) for group in
            ("pidgin", "mixed", "sarcastic", "adversarial")} == {
                "pidgin": 20, "mixed": 20, "sarcastic": 20, "adversarial": 20
            }

    by_group = defaultdict(lambda: [0, 0])
    confidences_right = []
    confidences_wrong = []
    for row in rows:
        prediction = rules_classify(row["text"])
        predicted_category = prediction.payment_category
        by_group[row["group"]][1] += 1
        correct = predicted_category == row["gold_payment_category"]
        if correct:
            by_group[row["group"]][0] += 1
            confidences_right.append(prediction.confidence)
        else:
            confidences_wrong.append(prediction.confidence)
        assert prediction.is_fraud == row["gold_is_fraud"], row["id"]

    for group, (correct, total) in sorted(by_group.items()):
        print(f"{group}: {correct}/{total} ({correct / total:.0%})")
    print(f"confidence_correct={sum(confidences_right) / len(confidences_right):.3f}")
    wrong_average = sum(confidences_wrong) / len(confidences_wrong) if confidences_wrong else None
    print(f"confidence_wrong={wrong_average:.3f}" if wrong_average is not None else "confidence_wrong=n/a (0 errors)")

    assert sum(correct for correct, _ in by_group.values()) / len(rows) >= 0.70
    confidences = {rules_classify(row["text"]).confidence for row in rows}
    assert len(confidences) >= 3
    if wrong_average is not None:
        assert sum(confidences_right) / len(confidences_right) > wrong_average
    assert "pidgin:" in capsys.readouterr().out
