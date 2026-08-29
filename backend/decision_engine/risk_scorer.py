"""
Risk Scorer — combines vital signals, symptoms, age, trends, and waiting exposure
into a continuous risk score used to determine priority.

Prototype scoring — not clinically validated.
"""
from .age_profiles import get_profile
from .normalizer import has_high_concern, has_elevated_risk, HIGH_CONCERN_SYMPTOMS
from .models import PatientState, VitalSnapshot


def score_vitals(vitals: VitalSnapshot, age_group: str) -> tuple[float, list]:
    """
    Returns (score 0.0–1.0, list of concerning vital strings).
    Higher = more concerning.
    """
    if vitals is None:
        return 0.0, []

    profile = get_profile(age_group)
    score = 0.0
    concerns = []

    def _check(value, key, label):
        nonlocal score
        if value is None:
            return
        thresholds = profile.get(key, {})
        if "critical_low" in thresholds and value <= thresholds["critical_low"]:
            score += 0.40
            concerns.append(f"{label} critically low ({value:.0f})")
        elif "critical_high" in thresholds and value >= thresholds["critical_high"]:
            score += 0.40
            concerns.append(f"{label} critically elevated ({value:.0f})")
        elif "low" in thresholds and value < thresholds["low"]:
            score += 0.15
            concerns.append(f"{label} low ({value:.0f})")
        elif "high" in thresholds and value > thresholds["high"]:
            score += 0.15
            concerns.append(f"{label} elevated ({value:.0f})")

    _check(vitals.heart_rate, "heart_rate", "Heart rate")
    _check(vitals.respiratory_rate, "respiratory_rate", "Respiratory rate")
    _check(vitals.spo2, "spo2", "SpO₂")
    _check(vitals.systolic_bp, "systolic_bp", "Systolic BP")
    _check(vitals.temperature, "temperature", "Temperature")

    if vitals.mental_status == "unresponsive":
        score += 0.50
        concerns.append("Unresponsive")
    elif vitals.mental_status == "confused":
        score += 0.25
        concerns.append("Altered consciousness / confused")

    return min(score, 1.0), concerns


def score_trends(current: VitalSnapshot, previous: VitalSnapshot, age_group: str) -> tuple[float, list]:
    """
    Detect deterioration trends between two vital snapshots.
    Returns (trend_score 0.0–0.5, list of trend strings).
    """
    if current is None or previous is None:
        return 0.0, []

    score = 0.0
    trends = []
    profile = get_profile(age_group)

    def _trend(curr_val, prev_val, key, label, worsening_direction="up"):
        nonlocal score
        if curr_val is None or prev_val is None:
            return
        delta = curr_val - prev_val
        thresholds = profile.get(key, {})
        normal_high = thresholds.get("high", float("inf"))
        normal_low = thresholds.get("low", float("-inf"))
        critical_high = thresholds.get("critical_high", float("inf"))
        critical_low = thresholds.get("critical_low", float("-inf"))

        # Determine if trending in the bad direction
        if worsening_direction == "up":
            worsening = delta > 0
        else:
            worsening = delta < 0

        # Big delta crossing critical threshold
        if worsening_direction == "up" and curr_val >= critical_high > prev_val:
            score += 0.30
            trends.append(f"{label} rapidly increasing to critical level")
        elif worsening_direction == "down" and curr_val <= critical_low < prev_val:
            score += 0.30
            trends.append(f"{label} rapidly decreasing to critical level")
        elif worsening and abs(delta) > (normal_high - normal_low) * 0.2:
            score += 0.10
            direction = "increasing" if delta > 0 else "decreasing"
            trends.append(f"{label} {direction}")

    _trend(current.heart_rate, previous.heart_rate, "heart_rate", "Heart rate", "up")
    _trend(current.respiratory_rate, previous.respiratory_rate, "respiratory_rate", "Respiratory rate", "up")
    _trend(current.spo2, previous.spo2, "spo2", "SpO₂", "down")
    _trend(current.systolic_bp, previous.systolic_bp, "systolic_bp", "Systolic BP", "down")
    _trend(current.temperature, previous.temperature, "temperature", "Temperature", "up")

    # Mental status worsening
    status_rank = {"alert": 0, "confused": 1, "unresponsive": 2}
    curr_rank = status_rank.get(current.mental_status, 0)
    prev_rank = status_rank.get(previous.mental_status, 0)
    if curr_rank > prev_rank:
        score += 0.35
        trends.append("Consciousness level deteriorating")

    return min(score, 0.50), trends


def score_symptoms(symptoms: list) -> tuple[float, list]:
    """Score based on normalized symptom tokens."""
    if not symptoms:
        return 0.0, []

    score = 0.0
    concerns = []

    if has_high_concern(symptoms):
        score += 0.45
        high = [s for s in symptoms if s in HIGH_CONCERN_SYMPTOMS]
        concerns.append(f"High-concern symptom: {high[0].replace('_', ' ')}")

    if has_elevated_risk(symptoms):
        score += 0.20
        concerns.append("Elevated-risk presentation")

    if "sudden_onset" in symptoms:
        score += 0.10
        concerns.append("Sudden onset")

    if "high_concern_language" in symptoms:
        score += 0.05
        concerns.append("Patient describes severity as extreme")

    return min(score, 0.70), concerns


def score_waiting_exposure(waiting_minutes: int, age_group: str, current_priority: str) -> tuple[float, list]:
    """Waiting too long at a given priority increases urgency."""
    from .age_profiles import get_wait_threshold
    threshold = get_wait_threshold(age_group, current_priority or "P4")
    if threshold == 0 or waiting_minutes <= 0:
        return 0.0, []

    ratio = waiting_minutes / threshold
    if ratio >= 2.0:
        return 0.20, [f"Waiting {waiting_minutes}m — significantly exceeds reassessment window"]
    elif ratio >= 1.0:
        return 0.12, [f"Waiting {waiting_minutes}m — exceeds reassessment threshold"]
    elif ratio >= 0.75:
        return 0.05, [f"Waiting {waiting_minutes}m — approaching reassessment threshold"]

    return 0.0, []


def score_age_risk(age_group: str) -> float:
    """Age-group baseline bonus."""
    profile = get_profile(age_group)
    return profile.get("age_risk_bonus", 0.0)


def compute_raw_risk(state: PatientState) -> tuple[float, list]:
    """
    Combine all risk signals into a single raw score (0.0–1.0).
    Returns (score, all_risk_factors).
    """
    factors = []
    total = 0.0

    # Vital score
    vital_score, vital_concerns = score_vitals(state.current_vitals, state.age_group)
    total += vital_score
    factors.extend(vital_concerns)

    # Trend score
    trend_score, trend_concerns = score_trends(
        state.current_vitals, state.previous_vitals, state.age_group
    )
    total += trend_score
    factors.extend(trend_concerns)

    # Symptom score
    sym_score, sym_concerns = score_symptoms(state.symptoms)
    total += sym_score
    factors.extend(sym_concerns)

    # Waiting exposure
    wait_score, wait_concerns = score_waiting_exposure(
        state.waiting_minutes, state.age_group, state.current_priority
    )
    total += wait_score
    factors.extend(wait_concerns)

    # Age bonus
    total += score_age_risk(state.age_group)

    return min(total, 1.0), factors
