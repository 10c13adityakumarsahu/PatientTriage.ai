"""
Safety Guardrails — hard rules that take precedence over model scores.
If safety rules disagree with scoring, safety wins.
Conflict is always visible and logged.

Design principle: prefer escalation/reassessment under uncertainty.
"""
from .models import PatientState, VitalSnapshot
from .normalizer import has_high_concern
from .age_profiles import get_profile


def check_critical_vitals(vitals: VitalSnapshot, age_group: str) -> list:
    """Returns list of critical vital flags."""
    if vitals is None:
        return []
    profile = get_profile(age_group)
    flags = []

    def _check_critical(val, key, label):
        if val is None:
            return
        t = profile.get(key, {})
        if "critical_low" in t and val <= t["critical_low"]:
            flags.append(f"CRITICAL: {label} {val:.0f} at or below critical threshold")
        if "critical_high" in t and val >= t["critical_high"]:
            flags.append(f"CRITICAL: {label} {val:.0f} at or above critical threshold")

    _check_critical(vitals.heart_rate, "heart_rate", "Heart rate")
    _check_critical(vitals.respiratory_rate, "respiratory_rate", "Respiratory rate")
    _check_critical(vitals.spo2, "spo2", "SpO₂")
    _check_critical(vitals.systolic_bp, "systolic_bp", "Systolic BP")

    if vitals.mental_status == "unresponsive":
        flags.append("CRITICAL: Patient unresponsive")

    return flags


def apply_guardrails(
    state: PatientState,
    proposed_priority: str,
    confidence: float,
    risk_factors: list,
    uncertainty_flags: list,
) -> tuple[str, str, bool, str]:
    """
    Returns (final_priority, safety_state, requires_human_review, safety_note).

    Safety rules can only escalate priority, never silently downgrade.
    """
    priority = proposed_priority
    safety_state = "GREEN"
    requires_review = False
    notes = []

    # 1. Critical vital signs → force P1
    critical_flags = check_critical_vitals(state.current_vitals, state.age_group)
    if critical_flags:
        if priority not in ("P1",):
            notes.append(f"Safety override: critical vitals detected → escalated to P1")
            priority = "P1"
        safety_state = "RED"
        requires_review = True

    # 2. High-concern symptoms → at minimum P2
    if has_high_concern(state.symptoms):
        if priority in ("P3", "P4", "P5"):
            notes.append("Safety override: high-concern symptom → minimum P2")
            priority = "P2"
        if safety_state == "GREEN":
            safety_state = "YELLOW"
        requires_review = True

    # 3. Missing history → cannot confidently downgrade below P3
    if not state.history_available and priority in ("P4", "P5") and confidence < 0.70:
        notes.append("Safety override: missing history with low confidence → minimum P3")
        priority = "P3"
        if safety_state == "GREEN":
            safety_state = "YELLOW"
        requires_review = True

    # 4. Low confidence → flag for human review
    if confidence < 0.60:
        if safety_state == "GREEN":
            safety_state = "YELLOW"
        requires_review = True
        notes.append("Low confidence — human review recommended")

    # 5. Conflicting signals → cannot silently downgrade
    if state.conflicting_signals:
        # Prevent downgrade from previous priority if signals conflict
        prev_priority = state.current_priority
        priority_order = {"P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5}
        if prev_priority and priority_order.get(priority, 5) > priority_order.get(prev_priority, 5):
            notes.append(
                f"Safety: conflicting signals — prevented downgrade from {prev_priority} to {priority}"
            )
            priority = prev_priority
        if safety_state == "GREEN":
            safety_state = "YELLOW"
        requires_review = True

    # 6. Clinician override — AI must not silently overwrite
    if state.clinician_overridden:
        # Keep clinician's priority, just note it
        notes.append("Clinician override active — AI recommendation advisory only")
        requires_review = False  # clinician already reviewed

    # 7. Mental status change → escalate if confused/unresponsive
    if state.current_vitals and state.current_vitals.mental_status in ("confused", "unresponsive"):
        if priority in ("P4", "P5"):
            priority = "P3"
            notes.append("Safety: altered mental status → minimum P3")
        if safety_state == "GREEN":
            safety_state = "YELLOW"

    return priority, safety_state, requires_review, "; ".join(notes)
