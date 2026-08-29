"""
Confidence Calculator — estimates certainty in the recommendation.
Confidence represents system certainty, NOT patient safety.
Lower confidence → more uncertainty visible to clinician.

Prototype thresholds only.
"""
from .models import PatientState


# Prototype confidence bands
HIGH_CONFIDENCE = 0.80
MEDIUM_CONFIDENCE = 0.60


def compute_confidence(state: PatientState) -> tuple[float, list, list]:
    """
    Returns (confidence 0.0–1.0, uncertainty_flags, missing_fields).
    """
    confidence = 1.0
    flags = []
    missing = list(state.missing_fields)  # start with already-known missing fields

    # Missing history — significant uncertainty increase per safety rules:
    # incomplete info must NOT be treated as low risk
    if not state.history_available:
        confidence -= 0.25
        flags.append("Medical history unavailable — increases uncertainty")
        missing.append("medical_history")

    # Missing vitals entirely
    if state.current_vitals is None:
        confidence -= 0.25
        flags.append("No vital signs recorded")
        missing.append("vital_signs")
    else:
        v = state.current_vitals
        missing_vitals = []
        if v.heart_rate is None:
            missing_vitals.append("heart_rate")
        if v.spo2 is None:
            missing_vitals.append("spo2")
        if v.respiratory_rate is None:
            missing_vitals.append("respiratory_rate")
        if v.systolic_bp is None:
            missing_vitals.append("systolic_bp")

        if missing_vitals:
            confidence -= 0.05 * len(missing_vitals)
            flags.append(f"Missing vitals: {', '.join(missing_vitals)}")
            missing.extend(missing_vitals)

    # No symptoms recorded
    if not state.symptoms:
        confidence -= 0.15
        flags.append("No symptoms recorded — relying on vitals only")
        missing.append("symptoms")

    # Conflicting signals — ambiguity must surface as uncertainty (safety rule)
    if state.conflicting_signals:
        confidence -= 0.15 * len(state.conflicting_signals)
        for conflict in state.conflicting_signals:
            flags.append(f"Conflicting signal: {conflict}")

    # Ambiguous complaint (chief complaint is very short or generic)
    complaint = (state.chief_complaint or "").lower().strip()
    if len(complaint) < 5 or complaint in {"pain", "unwell", "ill", "sick", "other"}:
        confidence -= 0.10
        flags.append("Chief complaint is non-specific")

    # No prior assessments (first time)
    if state.prior_assessments_count == 0:
        confidence -= 0.05
        flags.append("First assessment — limited baseline")

    # Ensure bounds
    confidence = max(0.10, min(1.0, confidence))

    return confidence, flags, list(set(missing))


def confidence_label(confidence: float) -> str:
    if confidence >= HIGH_CONFIDENCE:
        return "high"
    elif confidence >= MEDIUM_CONFIDENCE:
        return "medium"
    return "low"
