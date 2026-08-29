"""
Priority Mapper — converts raw risk score (0.0–1.0) to P1–P5 operational priority.
Thresholds are prototype demonstration values, not clinical standards.
"""

# Priority score thresholds
PRIORITY_THRESHOLDS = [
    (0.75, "P1"),  # Immediate
    (0.55, "P2"),  # Very Urgent
    (0.35, "P3"),  # Urgent
    (0.15, "P4"),  # Less Urgent
    (0.00, "P5"),  # Non-Urgent
]

PRIORITY_LABELS = {
    "P1": "Immediate",
    "P2": "Very Urgent",
    "P3": "Urgent",
    "P4": "Less Urgent",
    "P5": "Non-Urgent",
}

PRIORITY_ACTIONS = {
    "P1": "immediate_intervention",
    "P2": "urgent_clinician_review",
    "P3": "expedited_assessment",
    "P4": "routine_assessment",
    "P5": "standard_care",
}

PRIORITY_DESTINATIONS = {
    "P1": "resuscitation",
    "P2": "general_emergency",
    "P3": "general_emergency",
    "P4": "fast_track",
    "P5": "fast_track",
}


def score_to_priority(score: float) -> str:
    for threshold, priority in PRIORITY_THRESHOLDS:
        if score >= threshold:
            return priority
    return "P5"


def priority_to_action(priority: str) -> str:
    return PRIORITY_ACTIONS.get(priority, "standard_care")


def priority_to_destination(priority: str) -> str:
    return PRIORITY_DESTINATIONS.get(priority, "fast_track")


def priority_label(priority: str) -> str:
    return PRIORITY_LABELS.get(priority, "Unknown")
