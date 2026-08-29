"""
Explainer — generates concise, human-readable explanation of a recommendation.
Shows top 2–4 most important drivers. Not a wall of model output.
"""


def generate_explanation(
    risk_factors: list,
    uncertainty_flags: list,
    missing_fields: list,
    priority: str,
    confidence: float,
    safety_note: str = "",
) -> dict:
    """
    Returns a structured explanation dict for the clinician.
    """
    # Deduplicate and pick top factors
    seen = set()
    top_factors = []
    for f in risk_factors:
        if f not in seen:
            seen.add(f)
            top_factors.append(f)
        if len(top_factors) >= 4:
            break

    # Build uncertainty summary
    unc_summary = []
    for flag in uncertainty_flags[:3]:
        unc_summary.append(flag)

    if missing_fields:
        unc_summary.append(f"Data gaps: {', '.join(missing_fields[:3])}")

    return {
        "top_factors": top_factors,
        "uncertainty_summary": unc_summary,
        "confidence_pct": round(confidence * 100),
        "safety_note": safety_note if safety_note else None,
        "why_this_priority": _build_why(priority, top_factors),
    }


def _build_why(priority: str, factors: list) -> str:
    descriptions = {
        "P1": "Patient presents with immediately life-threatening signals.",
        "P2": "Patient presents with very urgent signals requiring rapid assessment.",
        "P3": "Patient has significant clinical signals requiring expedited assessment.",
        "P4": "Patient is stable but requires routine clinical assessment.",
        "P5": "Patient presentation is non-urgent; standard care pathway appropriate.",
    }
    base = descriptions.get(priority, "")
    if factors:
        return f"{base} Key signals: {'; '.join(factors[:2])}."
    return base
