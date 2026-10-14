"""
Age-aware configuration profiles.
Prototype thresholds — not clinically validated for real use.
These are demonstration values only.
"""

# Vital thresholds by age group
# Values are (min_normal, max_normal) — outside = concerning
AGE_PROFILES = {
    "pediatric": {
        "heart_rate": {"low": 70, "high": 130, "critical_low": 50, "critical_high": 180},
        "respiratory_rate": {"low": 20, "high": 40, "critical_low": 10, "critical_high": 60},
        "spo2": {"low": 95, "critical_low": 90},
        "systolic_bp": {"low": 80, "high": 120, "critical_low": 60, "critical_high": 140},
        "temperature": {"low": 36.1, "high": 37.9, "critical_low": 35.0, "critical_high": 39.5},
        # Safe wait window (minutes) per priority before reassessment trigger
        "wait_thresholds": {"P1": 0, "P2": 10, "P3": 30, "P4": 90, "P5": 180},
        "age_risk_bonus": 0.10,  # extra risk weight for pediatric
    },
    "adult": {
        "heart_rate": {"low": 60, "high": 100, "critical_low": 40, "critical_high": 150},
        "respiratory_rate": {"low": 12, "high": 20, "critical_low": 8, "critical_high": 30},
        "spo2": {"low": 95, "critical_low": 90},
        "systolic_bp": {"low": 90, "high": 140, "critical_low": 70, "critical_high": 180},
        "temperature": {"low": 36.1, "high": 37.9, "critical_low": 35.0, "critical_high": 39.5},
        "wait_thresholds": {"P1": 0, "P2": 15, "P3": 30, "P4": 60, "P5": 120},
        "age_risk_bonus": 0.0,
    },
    "geriatric": {
        "heart_rate": {"low": 55, "high": 95, "critical_low": 40, "critical_high": 130},
        "respiratory_rate": {"low": 12, "high": 22, "critical_low": 8, "critical_high": 28},
        "spo2": {"low": 94, "critical_low": 88},
        "systolic_bp": {"low": 100, "high": 150, "critical_low": 80, "critical_high": 200},
        "temperature": {"low": 35.5, "high": 37.5, "critical_low": 34.5, "critical_high": 38.5},
        "wait_thresholds": {"P1": 0, "P2": 10, "P3": 20, "P4": 45, "P5": 90},
        "age_risk_bonus": 0.15,  # geriatric patients carry higher baseline risk
    },
}


def get_profile(age_group: str) -> dict:
    """Return age-group configuration. Defaults to adult if unknown."""
    return AGE_PROFILES.get(age_group, AGE_PROFILES["adult"])


def get_wait_threshold(age_group: str, priority: str) -> int:
    """Minutes before a waiting patient at this priority should be reassessed."""
    profile = get_profile(age_group)
    return profile["wait_thresholds"].get(priority, 60)
