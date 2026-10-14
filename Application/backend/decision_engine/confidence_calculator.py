"""
Confidence Calculator — multi-component weighted confidence model.

Architecture follows the OS-scheduler analogy: each signal source is an
independent "process" contributing to the overall certainty estimate.
The final confidence score is the weighted combination, clamped to [0.10, 1.0].

Components (weights sum to 1.0):
  vital_completeness   0.25  — how complete and non-critical are the vitals
  history_quality      0.20  — is medical history available and substantive
  symptom_clarity      0.20  — are symptoms specific and mappable
  signal_coherence     0.15  — no conflicting signals
  assessment_baseline  0.05  — first-time vs repeat assessment
  age_risk_factor      0.10  — high-risk age group without full data
  comorbidity_context  0.05  — known comorbidities that affect interpretation

Returns:
  (confidence: float,           — final normalized score [0.10, 1.0]
   uncertainty_flags: list,     — human-readable flags
   missing_fields: list,        — missing data keys
   confidence_breakdown: dict)  — per-component scores for tooltip display

Safety constraints (from AGENTS.md):
  - Missing information must REDUCE confidence, not reduce risk
  - Conflicting signals must surface as uncertainty, never silently resolve
  - Prefer escalation/reassessment under uncertainty

Prototype only — not clinically validated.
"""
from __future__ import annotations
from typing import Optional
from .models import PatientState


# ─────────────────────────────────────────────────────────────────────────────
# Band thresholds
# ─────────────────────────────────────────────────────────────────────────────
HIGH_CONFIDENCE   = 0.80
MEDIUM_CONFIDENCE = 0.60


# ─────────────────────────────────────────────────────────────────────────────
# Component weights (must sum to 1.0)
# ─────────────────────────────────────────────────────────────────────────────
COMPONENT_WEIGHTS = {
    "vital_completeness":   0.25,
    "history_quality":      0.20,
    "symptom_clarity":      0.20,
    "signal_coherence":     0.15,
    "assessment_baseline":  0.05,
    "age_risk_factor":      0.10,
    "comorbidity_context":  0.05,
}

# Keywords in history text that indicate known risk-modifying comorbidities
COMORBIDITY_KEYWORDS = [
    "diabetes", "hypertension", "heart failure", "chf", "afib", "anticoagulant",
    "warfarin", "copd", "asthma", "renal failure", "ckd", "liver disease",
    "cirrhosis", "cancer", "immunocompromised", "hiv", "epilepsy",
    "prior stroke", "tia", "prior mi", "stent", "bypass", "dementia",
    "parkinson", "bleeding disorder", "haemophilia", "sickle cell",
    "transplant", "steroid", "dialysis",
]

# Words in a chief complaint that indicate non-specific / vague presentation
_VAGUE_COMPLAINT_WORDS = {
    "pain", "unwell", "ill", "sick", "other", "something", "issue",
    "problem", "complaint", "discomfort",
}


# ─────────────────────────────────────────────────────────────────────────────
# Per-component scorers
# Each returns (component_score: float [0,1], deduction_reason: str | None)
# component_score = 1.0 means full confidence contribution from this component
# ─────────────────────────────────────────────────────────────────────────────

def _score_vital_completeness(state: PatientState) -> tuple[float, Optional[str], list]:
    """
    Full vitals present and non-missing → 1.0
    Missing vitals reduce proportionally.
    No vitals at all → 0.0
    """
    missing_vitals = []

    if state.current_vitals is None:
        return 0.0, "No vital signs recorded — major uncertainty source", ["vital_signs"]

    v = state.current_vitals
    vital_fields = {
        "heart_rate": v.heart_rate,
        "spo2": v.spo2,
        "respiratory_rate": v.respiratory_rate,
        "systolic_bp": v.systolic_bp,
        "temperature": v.temperature,
    }

    missing = [k for k, val in vital_fields.items() if val is None]
    missing_vitals.extend(missing)

    if not missing:
        return 1.0, None, []

    # Proportional deduction: each missing vital removes 1/5 of the component score
    completeness = 1.0 - (len(missing) / len(vital_fields))
    reason = f"Missing vitals: {', '.join(missing)}"
    return max(0.0, completeness), reason, missing_vitals


def _score_history_quality(state: PatientState) -> tuple[float, Optional[str], list]:
    """
    Full history available and substantive → 1.0
    History unavailable → 0.0 (major uncertainty)
    History present but very short → 0.5
    """
    if not state.history_available:
        return 0.0, "Medical history unavailable — cannot assess risk modifiers", ["medical_history"]

    hist = (state.relevant_history or "").strip()
    if len(hist) < 10:
        return 0.40, "Medical history present but minimal/empty content", ["history_content"]
    if len(hist) < 50:
        return 0.70, "Medical history brief — limited risk modifier context", []

    return 1.0, None, []


def _score_symptom_clarity(state: PatientState) -> tuple[float, Optional[str], list]:
    """
    Specific symptom tokens present → 1.0
    No symptoms but vitals present → 0.5
    Neither → 0.0 (effectively caught by vital_completeness too)
    """
    if not state.symptoms:
        if state.current_vitals is not None:
            return 0.50, "No symptoms recorded — assessment relies on vitals only", ["symptoms"]
        return 0.20, "No symptoms recorded and no vitals — minimal clinical data", ["symptoms"]

    complaint = (state.chief_complaint or "").lower().strip()
    complaint_words = set(complaint.split())

    # Vague complaint: all words in vague set
    if not complaint or complaint_words.issubset(_VAGUE_COMPLAINT_WORDS):
        return 0.60, "Chief complaint is non-specific — symptom tokens present but complaint vague", []

    # Good: symptoms + specific complaint
    return 1.0, None, []


def _score_signal_coherence(state: PatientState) -> tuple[float, Optional[str]]:
    """
    No conflicting signals → 1.0
    Each conflict reduces score. Safety rule: conflicts must NOT be resolved silently.
    """
    if not state.conflicting_signals:
        return 1.0, None

    n = len(state.conflicting_signals)
    # Each conflict costs 0.20, capped at 0.80 deduction (floor at 0.20)
    score = max(0.20, 1.0 - (n * 0.20))
    reasons = [f"Conflicting signal: {c}" for c in state.conflicting_signals]
    return score, "; ".join(reasons)


def _score_assessment_baseline(state: PatientState) -> tuple[float, Optional[str]]:
    """
    Prior assessments provide baseline context.
    First assessment is inherently less certain.
    """
    count = state.prior_assessments_count
    if count == 0:
        return 0.50, "First assessment — no prior baseline for comparison"
    if count == 1:
        return 0.80, None
    return 1.0, None


def _score_age_risk_factor(state: PatientState) -> tuple[float, Optional[str]]:
    """
    High-risk age groups (pediatric/geriatric) without full vitals and history
    carry additional uncertainty — atypical presentations are common.
    """
    high_risk = state.age_group in ("pediatric", "geriatric")
    vitals_incomplete = state.current_vitals is None
    history_absent = not state.history_available

    if not high_risk:
        return 1.0, None

    if vitals_incomplete and history_absent:
        return 0.20, f"{state.age_group.capitalize()} patient — missing vitals AND history; atypical presentations likely"
    if vitals_incomplete or history_absent:
        return 0.60, f"{state.age_group.capitalize()} patient — incomplete data; risk of atypical presentation"

    return 0.90, f"{state.age_group.capitalize()} patient — data adequate but age-related uncertainty remains"


def _score_comorbidity_context(state: PatientState) -> tuple[float, Optional[str]]:
    """
    Known comorbidities detected in history increase interpretation complexity
    and reduce certainty slightly (more potential confounders).
    However, KNOWN comorbidities are better than UNKNOWN — having the data is good.
    Score reflects whether comorbidities were found (known → moderate confidence)
    vs not searched (no history → handled by history_quality).
    """
    if not state.history_available:
        return 0.0, "Cannot assess comorbidity status due to missing medical history"

    if not state.relevant_history:
        return 0.80, "No comorbidity details recorded in patient profile"

    hist_lower = (state.relevant_history or "").lower()
    found = [kw for kw in COMORBIDITY_KEYWORDS if kw in hist_lower]

    if not found:
        return 1.0, None   # Clean history — full contribution

    # Comorbidities found: slight reduction because they modulate interpretation
    # More comorbidities = more complex picture = slightly lower certainty
    score = max(0.60, 1.0 - (len(found) * 0.05))
    return score, f"Comorbidities noted in history: {', '.join(found[:4])}"


# ─────────────────────────────────────────────────────────────────────────────
# Main confidence computation
# ─────────────────────────────────────────────────────────────────────────────

def compute_confidence(state: PatientState) -> tuple[float, list, list, dict]:
    """
    Compute multi-component weighted confidence score.

    Returns:
      confidence       — final score [0.10, 1.0]
      uncertainty_flags — list of human-readable flag strings
      missing_fields   — list of missing data field names
      breakdown        — dict of component scores for UI tooltip
    """
    flags: list[str] = []
    missing: list[str] = list(state.missing_fields)

    # ── Run each component scorer ────────────────────────────────────────────
    vital_score, vital_reason, vital_missing = _score_vital_completeness(state)
    hist_score,  hist_reason,  hist_missing  = _score_history_quality(state)
    sym_score,   sym_reason,   sym_missing   = _score_symptom_clarity(state)
    coh_score,   coh_reason                  = _score_signal_coherence(state)
    base_score,  base_reason                 = _score_assessment_baseline(state)
    age_score,   age_reason                  = _score_age_risk_factor(state)
    morb_score,  morb_reason                 = _score_comorbidity_context(state)

    # Collect flags and missing fields
    for reason, miss in [
        (vital_reason, vital_missing),
        (hist_reason,  hist_missing),
        (sym_reason,   sym_missing),
    ]:
        if reason:
            flags.append(reason)
        missing.extend(miss)

    for reason in [coh_reason, base_reason, age_reason, morb_reason]:
        if reason:
            flags.append(reason)

    # ── Weighted combination ─────────────────────────────────────────────────
    w = COMPONENT_WEIGHTS
    weighted_sum = (
        vital_score * w["vital_completeness"] +
        hist_score  * w["history_quality"] +
        sym_score   * w["symptom_clarity"] +
        coh_score   * w["signal_coherence"] +
        base_score  * w["assessment_baseline"] +
        age_score   * w["age_risk_factor"] +
        morb_score  * w["comorbidity_context"]
    )

    # Normalize to [0.10, 1.0]
    confidence = max(0.10, min(1.0, weighted_sum))

    # ── Build breakdown for tooltip ──────────────────────────────────────────
    breakdown = {
        "components": {
            "vital_completeness": {
                "score": round(vital_score, 3),
                "weight": w["vital_completeness"],
                "contribution": round(vital_score * w["vital_completeness"], 3),
                "label": "Vital Completeness",
                "description": "How complete the patient's vital sign set is",
                "flag": vital_reason,
            },
            "history_quality": {
                "score": round(hist_score, 3),
                "weight": w["history_quality"],
                "contribution": round(hist_score * w["history_quality"], 3),
                "label": "History Quality",
                "description": "Availability and substance of medical history",
                "flag": hist_reason,
            },
            "symptom_clarity": {
                "score": round(sym_score, 3),
                "weight": w["symptom_clarity"],
                "contribution": round(sym_score * w["symptom_clarity"], 3),
                "label": "Symptom Clarity",
                "description": "Specificity of symptoms and chief complaint",
                "flag": sym_reason,
            },
            "signal_coherence": {
                "score": round(coh_score, 3),
                "weight": w["signal_coherence"],
                "contribution": round(coh_score * w["signal_coherence"], 3),
                "label": "Signal Coherence",
                "description": "Absence of conflicting clinical signals",
                "flag": coh_reason,
            },
            "assessment_baseline": {
                "score": round(base_score, 3),
                "weight": w["assessment_baseline"],
                "contribution": round(base_score * w["assessment_baseline"], 3),
                "label": "Assessment Baseline",
                "description": "Prior assessment history for trend comparison",
                "flag": base_reason,
            },
            "age_risk_factor": {
                "score": round(age_score, 3),
                "weight": w["age_risk_factor"],
                "contribution": round(age_score * w["age_risk_factor"], 3),
                "label": "Age-Risk Factor",
                "description": "Age group uncertainty (paediatric/geriatric have atypical presentations)",
                "flag": age_reason,
            },
            "comorbidity_context": {
                "score": round(morb_score, 3),
                "weight": w["comorbidity_context"],
                "contribution": round(morb_score * w["comorbidity_context"], 3),
                "label": "Comorbidity Context",
                "description": "Detected comorbidities that modulate clinical interpretation",
                "flag": morb_reason,
            },
        },
        "final_score": round(confidence, 3),
        "final_pct": round(confidence * 100),
        "uncertainty_flags": flags,
        "missing_fields": list(set(missing)),
        "interpretation": _interpret_confidence(confidence),
        "clinical_note": _clinical_note(confidence, flags),
    }

    return confidence, flags, list(set(missing)), breakdown


def _interpret_confidence(score: float) -> str:
    if score >= HIGH_CONFIDENCE:
        return "High confidence — recommendation reflects strong and consistent clinical signals."
    if score >= MEDIUM_CONFIDENCE:
        return "Medium confidence — some data gaps or mild signal uncertainty present."
    if score >= 0.40:
        return "Low confidence — significant data gaps; recommendation is conservative. Clinician review recommended."
    return "Very low confidence — critical data missing. Override and clinical judgment essential."


def _clinical_note(score: float, flags: list) -> str:
    if score >= HIGH_CONFIDENCE:
        return "Clinical decision support is reliable for this presentation."
    flag_count = len(flags)
    if flag_count == 0:
        return "Review assessment inputs for completeness."
    return (
        f"{flag_count} uncertainty factor{'s' if flag_count != 1 else ''} detected. "
        "Consider resolving missing data before acting on recommendation. "
        "Override always available."
    )


def confidence_label(confidence: float) -> str:
    if confidence >= HIGH_CONFIDENCE:
        return "high"
    elif confidence >= MEDIUM_CONFIDENCE:
        return "medium"
    return "low"
