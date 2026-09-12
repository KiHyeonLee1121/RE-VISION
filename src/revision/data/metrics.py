"""Part-level inspection metrics; REVIEW/ERROR must remain visible in reported coverage."""

from collections import Counter


def evaluate(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("no evaluation results")
    counts: Counter = Counter()
    ids = set()
    durations = []
    views = []
    for row in rows:
        if row["part_id"] in ids:
            raise ValueError("evaluation expects one inspection per part")
        ids.add(row["part_id"])
        label, verdict = row["label"], row["verdict"]
        if label not in {"clean", "defective"} or verdict not in {
            "PASS",
            "FAIL",
            "REVIEW",
            "ERROR",
        }:
            raise ValueError("invalid label or verdict")
        counts[(label, verdict)] += 1
        durations.append(row["duration_ms"])
        views.append(row["view_count"])

    def ratio(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    clean = sum(n for (label, _), n in counts.items() if label == "clean")
    defective = len(rows) - clean
    automatic = sum(n for (_, verdict), n in counts.items() if verdict in {"PASS", "FAIL"})
    durations.sort()

    def percentile(p: float) -> float:
        i = (len(durations) - 1) * p
        lo = int(i)
        hi = min(lo + 1, len(durations) - 1)
        return durations[lo] + (durations[hi] - durations[lo]) * (i - lo)

    return {
        "part_count": len(rows),
        "automatic_coverage": automatic / len(rows),
        "defect_recall": ratio(counts[("defective", "FAIL")], defective),
        "false_pass_rate": ratio(counts[("defective", "PASS")], defective),
        "false_fail_rate": ratio(counts[("clean", "FAIL")], clean),
        "review_rate": sum(n for (_, v), n in counts.items() if v == "REVIEW") / len(rows),
        "error_rate": sum(n for (_, v), n in counts.items() if v == "ERROR") / len(rows),
        "mean_views": sum(views) / len(views),
        "latency_ms": {"p50": percentile(0.5), "p95": percentile(0.95), "p99": percentile(0.99)},
        "confusion": {f"{label}->{v}": n for (label, v), n in sorted(counts.items())},
    }
