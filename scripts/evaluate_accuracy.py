
import argparse
import csv
import json
from pathlib import Path


def evaluate(scale):
    folder = Path("data") / scale

    ground_truth_path = folder / "ground_truth.csv"
    validation_path = folder / "validation_report.json"

    with ground_truth_path.open(
        newline="", encoding="utf-8"
    ) as file:
        labels = list(csv.DictReader(file))

    with validation_path.open(
        encoding="utf-8"
    ) as file:
        report = json.load(file)

    # Match both issue type and record ID.
    expected = {
        (row["issue_type"], row["record_id"])
        for row in labels
        if row["expected_label"] == "1"
    }

    detected = {
        (row["issue_type"], row["record_id"])
        for row in report["issues"]
    }

    matched = expected & detected
    missed = expected - detected
    extra = detected - expected

    tp = len(matched)
    fp = len(extra)
    fn = len(missed)

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0

    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall else 0.0
    )

    results = {
        "dataset": scale,
        "ground_truth_count": len(expected),
        "detected_unique_issues": len(detected),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "matched": [
            {"issue_type": t, "record_id": r}
            for t, r in sorted(matched)
        ],
        "missed": [
            {"issue_type": t, "record_id": r}
            for t, r in sorted(missed)
        ],
        "additional_findings": [
            {"issue_type": t, "record_id": r}
            for t, r in sorted(extra)
        ],
    }

    output_path = folder / "evaluation_report.json"

    with output_path.open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(results, file, indent=2)

    print("\nANOMALY EVALUATION")
    print("------------------")
    print("True positives:", tp)
    print("Unmatched findings:", fp)
    print("False negatives:", fn)
    print(f"Precision: {precision:.2%}")
    print(f"Recall: {recall:.2%}")
    print(f"F1-score: {f1:.2%}")

    if missed:
        print("\nMissed ground-truth anomalies:")
        for issue_type, record_id in sorted(missed):
            print(issue_type, record_id)

    if extra:
        print("\nAdditional validation findings:")
        for issue_type, record_id in sorted(extra):
            print(issue_type, record_id)

    print("\nReport:", output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scale",
        choices=["starter_anomalies", "full_anomalies"],
        default="starter_anomalies"
    )

    args = parser.parse_args()
    evaluate(args.scale)
