"""
Symptom Normalizer — maps free-text to controlled vocabulary tokens.
Preserves original text for auditability.
"""

# Controlled symptom vocabulary
SYMPTOM_TOKENS = {
    # Chest / Cardiac
    "chest pain": "chest_pain",
    "chest discomfort": "chest_pain",
    "chest tightness": "chest_tightness",
    "crushing chest": "chest_pain_high_concern",
    "heart racing": "palpitations",
    "palpitations": "palpitations",

    # Respiratory
    "shortness of breath": "shortness_of_breath",
    "breathless": "shortness_of_breath",
    "difficulty breathing": "shortness_of_breath",
    "sob": "shortness_of_breath",
    "wheeze": "wheeze",
    "wheezing": "wheeze",
    "cough": "cough",

    # Neurological
    "confusion": "altered_consciousness",
    "confused": "altered_consciousness",
    "unresponsive": "unresponsive",
    "seizure": "seizure",
    "fitting": "seizure",
    "headache": "headache",
    "severe headache": "severe_headache",
    "worst headache": "severe_headache_thunderclap",
    "dizziness": "dizziness_or_syncope_signal",
    "feeling faint": "dizziness_or_syncope_signal",
    "syncope": "syncope",
    "loss of consciousness": "syncope",
    "weakness": "weakness",

    # Abdominal
    "abdominal pain": "abdominal_pain",
    "stomach pain": "abdominal_pain",
    "nausea": "nausea",
    "vomiting": "vomiting",

    # Trauma
    "laceration": "laceration",
    "cut": "laceration",
    "bleeding": "active_bleeding",
    "fracture": "fracture",
    "fall": "fall",

    # Systemic
    "fever": "fever",
    "high temperature": "fever",
    "sepsis": "sepsis_concern",
    "allergic reaction": "allergic_reaction",
    "anaphylaxis": "anaphylaxis",

    # Pediatric-relevant
    "rash": "rash",
    "meningitis": "meningitis_concern",
    "not feeding": "pediatric_feeding_concern",

    # High-concern language modifiers
    "worst": "high_concern_language",
    "severe": "high_concern_language",
    "crushing": "high_concern_language",
    "sudden": "sudden_onset",
    "sudden onset": "sudden_onset",
}

# Symptom tokens that are always high concern regardless of vitals
HIGH_CONCERN_SYMPTOMS = {
    "chest_pain_high_concern",
    "severe_headache_thunderclap",
    "unresponsive",
    "seizure",
    "syncope",
    "anaphylaxis",
    "sepsis_concern",
    "meningitis_concern",
}

# Symptom tokens that elevate risk score
ELEVATED_RISK_SYMPTOMS = {
    "chest_pain",
    "chest_tightness",
    "shortness_of_breath",
    "altered_consciousness",
    "active_bleeding",
    "severe_headache",
    "allergic_reaction",
}


def normalize_symptoms(raw_text: str, raw_list: list = None) -> tuple[list, list]:
    """
    Returns (normalized_tokens, extracted_flags).
    Preserves original for audit.
    """
    tokens = []
    flags = []

    # Process list input
    sources = list(raw_list or [])
    if raw_text:
        sources.append(raw_text.lower())

    combined = " ".join(str(s).lower() for s in sources)

    for phrase, token in SYMPTOM_TOKENS.items():
        if phrase in combined:
            if token not in tokens:
                tokens.append(token)

    # Extract flags
    for token in tokens:
        if token in HIGH_CONCERN_SYMPTOMS:
            flags.append("high_concern_symptom")
            break

    if "high_concern_language" in tokens:
        flags.append("high_concern_language_detected")

    if "sudden_onset" in tokens:
        flags.append("sudden_onset")

    return tokens, flags


def has_high_concern(tokens: list) -> bool:
    return bool(set(tokens) & HIGH_CONCERN_SYMPTOMS)


def has_elevated_risk(tokens: list) -> bool:
    return bool(set(tokens) & ELEVATED_RISK_SYMPTOMS)
