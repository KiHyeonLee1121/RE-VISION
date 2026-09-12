"""Explainable starting policy; replace with information-gain or learned selection later."""

from revision.domain import LightAction, Observation


class CoveragePolicy:
    def select(
        self, actions: tuple[LightAction, ...], observations: list[Observation]
    ) -> LightAction | None:
        used = {o.action.id for o in observations}
        candidates = [a for a in actions if a.id not in used]
        if not candidates:
            return None
        if not observations:
            return candidates[0]
        last = observations[-1]

        def priority(action: LightAction) -> tuple[float, float]:
            distances = [
                abs((action.direction_deg - o.action.direction_deg + 180) % 360 - 180)
                for o in observations
            ]
            # Glare -> dimmer light; darkness -> brighter light; otherwise angular coverage.
            brightness = 0.0
            if last.quality_reason == "overexposed":
                brightness = -action.intensity
            elif last.quality_reason == "underexposed":
                brightness = action.intensity
            return brightness, min(distances)

        return max(candidates, key=priority)
