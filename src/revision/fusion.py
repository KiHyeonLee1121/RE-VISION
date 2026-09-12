from revision.domain import Evidence, Observation


class MaxScoreFusion:
    """A defect seen in one valid view must not be averaged away by other views.

    This is a score-level baseline, not spatial fusion or Bayesian confidence.
    Its thresholds need part-level validation; more views can raise false positives.
    """

    def combine(self, observations: list[Observation]) -> Evidence:
        scores = [
            o.prediction.defect_score for o in observations if o.usable and o.prediction is not None
        ]
        if not scores:
            return Evidence(None, 1.0, 0)
        score = max(scores)
        return Evidence(score, 1.0 - abs(2.0 * score - 1.0), len(scores))
