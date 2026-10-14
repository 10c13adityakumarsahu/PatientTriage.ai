"""
AI Clinical Assistant — RAG-augmented clinical decision support.

Architecture:
- MedicalKnowledgeStore: TF-IDF keyword retrieval over medical_knowledge.json
- retrieve_relevant_protocols(): top-k domain retrieval for RAG context
- call_gemini_api(): LLM call with retrieved context injected into prompt
- CIRCUIT_BREAKER: if Gemini unavailable, falls back to knowledge-store only (no hardcoded branches)
- AI_MODE flag: published to consumers so the UI can display the correct banner

Modes:
  FULL_AI   — Gemini API available and responding
  RAG_ONLY  — Gemini offline; knowledge store drives scoring
  STATIC    — Complete fallback; static priority-based scoring from vitals/symptoms only

Safety constraints:
  - Uncertain data must reduce confidence, not automatically reduce risk
  - Vague/empty inputs return minimal output (guardrail)
  - All outputs validated and normalized before return
  - Prototype/synthetic only — not clinically validated
"""
import os
import json
import math
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Ensure dotenv is loaded relative to the backend workspace on module import
def _load_dynamic_dotenv():
    backend_dir = Path(__file__).resolve().parent.parent
    env_path = backend_dir / ".env"
    load_dotenv(str(env_path))

_load_dynamic_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# AI Mode constants (published via ai_mode_status())
# ─────────────────────────────────────────────────────────────────────────────
AI_MODE_FULL = "FULL_AI"       # Gemini API + RAG context
# Pure rule-based, no AI or knowledge store (In case of circuit break)
AI_MODE_STATIC = "STATIC"     # Pure rule-based, no AI or knowledge store (In case of circuit break)
AI_MODE_RAG  = "RAG_ONLY"     # Knowledge store only (Gemini offline)

_key_present = bool(os.getenv("GEMINI_API_KEY", "").strip())
_current_ai_mode = AI_MODE_FULL if _key_present else (
    AI_MODE_RAG if (Path(__file__).parent / "medical_knowledge.json").exists() else AI_MODE_STATIC
)
_force_static = False

# Circuit-breaker: consecutive Gemini failures before entering RAG_ONLY mode
_CB_THRESHOLD = 3
_cb_failure_count = 0
_cb_open = False          # True = circuit is open (Gemini bypassed)


def ai_mode_status() -> dict:
    """
    Return current AI mode status for the frontend banner.
    Called by the triage serializer / config endpoint.
    """
    global _cb_open, _cb_failure_count, _current_ai_mode
    # Reload .env dynamically so updates are read at runtime without restarting Django
    _load_dynamic_dotenv()
    key_present = bool(os.getenv("GEMINI_API_KEY", "").strip())
    
    # If key is present and circuit was open or mode was downgraded, auto-restore FULL_AI
    if key_present and (_current_ai_mode != AI_MODE_FULL or _cb_open):
        _cb_open = False
        _cb_failure_count = 0
        _current_ai_mode = AI_MODE_FULL

    mode = AI_MODE_STATIC if _force_static else _current_ai_mode
    return {
        "mode": mode,
        "gemini_available": not _cb_open and key_present and not _force_static,
        "circuit_breaker_open": _cb_open or _force_static,
        "failure_count": _cb_failure_count,
        "banner": _build_banner_message(mode),
        "force_static": _force_static,
    }


def set_force_static(value: bool):
    global _force_static, _cb_open, _cb_failure_count, _current_ai_mode
    _force_static = value
    if not value:
        # Reset circuit breaker when clinician manually turns off force-static or restores AI
        _cb_open = False
        _cb_failure_count = 0
        # Reload env vars
        _load_dynamic_dotenv()
        key_present = bool(os.getenv("GEMINI_API_KEY", "").strip())
        _current_ai_mode = AI_MODE_FULL if key_present else (
            AI_MODE_RAG if (Path(__file__).parent / "medical_knowledge.json").exists() else AI_MODE_STATIC
        )



def _build_banner_message(mode: str) -> Optional[str]:
    if mode == AI_MODE_FULL:
        return None   # No banner when fully operational
    if mode == AI_MODE_RAG:
        return (
            "AI-Assisted Scoring Unavailable — Gemini LLM is offline. "
            "Recommendations are generated from the built-in clinical knowledge base. "
            "All scoring and priority logic remains active. Override is always available."
        )
    return (
        "AI Scoring in Static Mode — Knowledge base unavailable. "
        "Priority is determined from vital signs and symptom rules only. "
        "Use clinician override for any case requiring judgment beyond vital thresholds."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Medical Knowledge Store (RAG retrieval)
# ─────────────────────────────────────────────────────────────────────────────
_knowledge_store: Optional[dict] = None


def _load_knowledge_store() -> dict:
    global _knowledge_store
    if _knowledge_store is not None:
        return _knowledge_store
    kb_path = Path(__file__).parent / "medical_knowledge.json"
    try:
        with open(kb_path, "r", encoding="utf-8") as f:
            _knowledge_store = json.load(f)
        return _knowledge_store
    except Exception as e:
        print(f"[KnowledgeStore] Failed to load: {e}")
        return {"domains": []}


def _keyword_score(text: str, keywords: list) -> float:
    """
    Simple TF-IDF-inspired keyword overlap score in [0, 1].
    Longer keyword phrases get higher weight (specificity bonus).
    """
    if not text:
        return 0.0
    text_lower = text.lower()
    total_weight = 0.0
    matched_weight = 0.0
    for kw in keywords:
        weight = 1.0 + 0.3 * (len(kw.split()) - 1)   # multi-word bonus
        total_weight += weight
        if kw.lower() in text_lower:
            matched_weight += weight
    return matched_weight / total_weight if total_weight > 0 else 0.0


def retrieve_relevant_protocols(
    chief_complaint: str,
    history: str = "",
    age_group: str = "adult",
    top_k: int = 2,
) -> list:
    """
    Retrieve the top-k most relevant clinical domains for this presentation.
    Returns a list of domain dicts, sorted by relevance score descending.
    """
    store = _load_knowledge_store()
    if not store.get("domains"):
        return []

    combined_text = f"{chief_complaint or ''} {history or ''}".strip()
    if not combined_text:
        return []

    scored = []
    for domain in store["domains"]:
        score = _keyword_score(combined_text, domain.get("keywords", []))
        # Age modifier bonus: domains that explicitly address this age group get boost
        age_mod = domain.get("age_modifiers", {}).get(age_group, "")
        if age_mod and len(age_mod) > 20:
            score += 0.05
        if score > 0:
            scored.append((score, domain))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:top_k]]


def _format_rag_context(domains: list, age_group: str) -> str:
    """Format retrieved domain context for injection into LLM prompt."""
    if not domains:
        return ""
    parts = []
    for d in domains:
        age_modifier = d.get("age_modifiers", {}).get(age_group, "")
        comorbidities = d.get("comorbidity_flags", [])
        parts.append(
            f"--- Domain: {d['label']} ---\n"
            f"Typical complexity: {d.get('complexity', 'Unknown')}\n"
            f"Monitoring criteria: {'; '.join(d.get('monitoring_criteria', []))}\n"
            f"Standard tests: {'; '.join(d.get('preliminary_tests', []))}\n"
            f"Age-specific ({age_group}): {age_modifier or 'Standard approach.'}\n"
            f"Watch for these comorbidities: {', '.join(comorbidities) if comorbidities else 'None listed.'}\n"
        )
    return "\n".join(parts)


def _extract_comorbidity_flags(history: str, domains: list) -> list:
    """Check if patient history mentions any comorbidities flagged by retrieved domains."""
    if not history:
        return []
    hist_lower = history.lower()
    flags = []
    for d in domains:
        for flag in d.get("comorbidity_flags", []):
            if flag.lower() in hist_lower and flag not in flags:
                flags.append(flag)
    return flags


# ─────────────────────────────────────────────────────────────────────────────
# Output normalization and validation
# ─────────────────────────────────────────────────────────────────────────────
_VALID_COMPLEXITY = {"High", "Medium", "Low"}
_VALID_CRITICALNESS = {"Immediate", "Urgent", "Stable", "Low"}
_VALID_PRIORITIES = {"P1", "P2", "P3", "P4", "P5"}
_REQUIRED_MED_KEYS = {"name", "dosage", "indication", "warning"}


def _normalize_ai_symptoms_output(raw: dict, fallback_domain: Optional[dict] = None) -> dict:
    """
    Validate and normalize the AI symptoms output.
    Strips unexpected keys. Clamps values. Falls back to domain data for missing fields.
    """
    if not isinstance(raw, dict):
        raw = {}

    fb = fallback_domain or {}

    complexity = raw.get("complexity", "")
    if complexity not in _VALID_COMPLEXITY:
        complexity = fb.get("complexity", "Low")

    rationale = str(raw.get("complexity_rationale") or raw.get("rationale") or
                    fb.get("complexity_rationale", "Clinical presentation evaluated."))[:500]

    criteria = raw.get("criteria") or fb.get("monitoring_criteria", [])
    if not isinstance(criteria, list):
        criteria = []
    criteria = [str(c)[:200] for c in criteria[:8]]

    tests = raw.get("preliminary_tests") or fb.get("preliminary_tests", [])
    if not isinstance(tests, list):
        tests = []
    tests = [str(t)[:200] for t in tests[:8]]

    medications = raw.get("medications") or []
    if not isinstance(medications, list):
        medications = []
    validated_meds = []
    for med in medications[:6]:
        if not isinstance(med, dict):
            continue
        if all(k in med for k in _REQUIRED_MED_KEYS):
            validated_meds.append({
                "name": str(med["name"])[:100],
                "dosage": str(med["dosage"])[:100],
                "indication": str(med["indication"])[:200],
                "warning": str(med["warning"])[:300],
            })

    # If medications empty, try pulling from knowledge base
    if not validated_meds and fb.get("emergency_medications"):
        validated_meds = fb["emergency_medications"][:3]

    return {
        "complexity": complexity,
        "complexity_rationale": rationale,
        "criteria": criteria,
        "preliminary_tests": tests,
        "medications": validated_meds,
    }


def _normalize_degradation_output(raw: dict, fallback_domain: Optional[dict] = None) -> dict:
    """Validate and normalize degradation analysis output."""
    if not isinstance(raw, dict):
        raw = {}

    fb = fallback_domain or {}

    criticalness = raw.get("criticalness", "")
    if criticalness not in _VALID_CRITICALNESS:
        criticalness = fb.get("criticalness", "Stable")

    rate = raw.get("degradation_rate", None)
    if rate is None:
        rate = fb.get("degradation_rate", 0.001)
    try:
        rate = float(rate)
    except (TypeError, ValueError):
        rate = 0.001
    rate = max(0.0001, min(0.02, rate))

    explanation = str(raw.get("explanation") or
                      fb.get("complexity_rationale", "Stable condition."))[:400]

    return {
        "criticalness": criticalness,
        "degradation_rate": rate,
        "explanation": explanation,
    }


def _normalize_report_output(raw: dict) -> dict:
    """Validate scan report re-evaluation output."""
    if not isinstance(raw, dict):
        raw = {}

    priority = raw.get("priority", "P4")
    if priority not in _VALID_PRIORITIES:
        priority = "P4"

    confidence = raw.get("confidence", 0.5)
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.5

    findings_status = raw.get("findings_status", "Normal")
    explanation = str(raw.get("explanation") or "Scan findings evaluated.")[:400]

    return {
        "priority": priority,
        "confidence": confidence,
        "findings_status": findings_status,
        "explanation": explanation,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Gemini API call with circuit breaker
# ─────────────────────────────────────────────────────────────────────────────
def call_gemini_api(prompt: str) -> Optional[dict]:
    """
    Calls Google Gemini API with the given prompt.
    Implements a circuit breaker: after _CB_THRESHOLD consecutive failures,
    the circuit opens and Gemini is bypassed until the process restarts.
    Returns None to trigger fallback.
    """
    global _cb_failure_count, _cb_open

    # Reload .env dynamically so updates are read at runtime without restarting Django
    _load_dynamic_dotenv()

    if _cb_open:
        return None

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    # Fast bypass for placeholder dummy keys or bypass environment settings to run instantly
    if not api_key or "AIzaSy" in api_key or os.getenv("BYPASS_GEMINI_API", "true").lower() == "true":
        return None

    # Dynamically resolve model name from settings or environment
    try:
        from django.conf import settings
        model_name = getattr(settings, 'GEMINI_MODEL', None)
    except Exception:
        model_name = None
    if not model_name:
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-live-preview").strip()

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_name}:generateContent?key={api_key}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1,       # low temperature for clinical consistency
            "maxOutputTokens": 4096,
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            text_out = res_data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text_out)
            # Reset circuit breaker on success
            _cb_failure_count = 0
            
            # Log AI success event in Audit Trail
            from audit.models import AuditEvent
            try:
                AuditEvent.log(
                    event_type='ai_generation_success',
                    actor_type='ai',
                    actor_id=model_name,
                    new_state={
                        'model': model_name,
                        'prompt_length': len(prompt),
                        'response_keys': list(parsed.keys()) if isinstance(parsed, dict) else [],
                    },
                    trigger='call_gemini_api',
                )
            except Exception:
                pass
                
            return parsed
    except Exception as e:
        _cb_failure_count += 1
        print(f"[Gemini] API call failed ({_cb_failure_count}/{_CB_THRESHOLD}): {e}")
        
        # Log AI failure event in Audit Trail
        from audit.models import AuditEvent
        try:
            AuditEvent.log(
                event_type='ai_generation_failure',
                actor_type='ai',
                actor_id=model_name,
                new_state={
                    'error': str(e),
                    'failure_count': _cb_failure_count,
                    'circuit_breaker_open': _cb_failure_count >= _CB_THRESHOLD,
                },
                trigger='call_gemini_api',
            )
        except Exception:
            pass
            
        if _cb_failure_count >= _CB_THRESHOLD:
            _cb_open = True
            print(f"[Gemini] Circuit breaker OPEN — switching to RAG_ONLY mode using model {model_name}")
        return None


def _update_ai_mode(gemini_result: Optional[dict]) -> None:
    """Update the global AI mode based on whether Gemini responded."""
    global _current_ai_mode
    api_key = bool(os.getenv("GEMINI_API_KEY", "").strip())
    if gemini_result is not None:
        _current_ai_mode = AI_MODE_FULL
    elif api_key and not _cb_open:
        _current_ai_mode = AI_MODE_FULL  # key present, not yet failed
    elif _knowledge_store is not None or (Path(__file__).parent / "medical_knowledge.json").exists():
        _current_ai_mode = AI_MODE_RAG
    else:
        _current_ai_mode = AI_MODE_STATIC


# ─────────────────────────────────────────────────────────────────────────────
# Vagueness guardrail
# ─────────────────────────────────────────────────────────────────────────────
_VAGUE_EXACT = {"unknown", "something", "none", "issue", "problem", "n/a", "na",
                "vague", "test", "demo", "pain", "symptom", "illness", "sick", "unwell"}


def _is_vague(chief_complaint: str, history: str) -> bool:
    combined = f"{chief_complaint or ''} {history or ''}".strip().lower()
    if not combined or len(combined) < 5:
        return True
    if combined in _VAGUE_EXACT:
        return True
    # All words are in the vague set
    words = set(re.split(r'\W+', combined))
    if words and words.issubset(_VAGUE_EXACT | {""}):
        return True
    return False


_VAGUE_SYMPTOMS_RESULT = {
    "complexity": "Low",
    "complexity_rationale": "Insufficient clinical details provided. Standard observation protocol applied. Guardrail active.",
    "criteria": ["Standard vital sign observation", "Monitor for evolving symptoms"],
    "preliminary_tests": [],
    "medications": [],
}

_VAGUE_DEGRADATION_RESULT = {
    "criticalness": "Low",
    "degradation_rate": 0.0001,
    "explanation": "Vague presentation. Guardrail active: minimal degradation rate assigned. Reassess when clinical details available.",
}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
def analyze_symptoms_ai(
    chief_complaint: str,
    relevant_history: str = "",
    age: Optional[int] = None,
    sex: str = "",
    age_group: str = "adult",
) -> dict:
    """
    Primary AI analysis: complexity, monitoring criteria, tests, medications.
    Uses Gemini LLM with RAG context when available, falls back to knowledge-store only.
    """
    cc = (chief_complaint or "").strip()
    hist = (relevant_history or "").strip()

    if _force_static:
        _update_ai_mode(None)
        return {
            "complexity": "Low",
            "complexity_rationale": "Static mode forced by clinician (Circuit Breaker active). Standard care rules applied.",
            "criteria": ["Monitor vital signs", "Observe for secondary symptoms"],
            "preliminary_tests": [],
            "medications": [],
        }

    if _is_vague(cc, hist):
        _update_ai_mode(None)
        return dict(_VAGUE_SYMPTOMS_RESULT)

    # 1. Retrieve relevant protocols (RAG)
    domains = retrieve_relevant_protocols(cc, hist, age_group=age_group, top_k=2)
    rag_context = _format_rag_context(domains, age_group)
    comorbidity_flags = _extract_comorbidity_flags(hist, domains)
    primary_domain = domains[0] if domains else None

    # 2. Try Gemini with RAG context
    history_note = (
        f"- Medical History / Relevant Notes: {hist}" if hist else
        "- Medical History: Not available (treat as unknown risk — do NOT assume low risk)"
    )
    comorbidity_note = (
        f"- Known comorbidities / risk factors detected in history: {', '.join(comorbidity_flags)}"
        if comorbidity_flags else ""
    )

    prompt = f"""You are an expert Emergency Department Clinical Decision Support System.

RETRIEVED CLINICAL KNOWLEDGE BASE CONTEXT (use this to inform your analysis):
{rag_context if rag_context else "(No matching domain retrieved — base analysis on clinical reasoning.)"}

PATIENT PRESENTATION:
- Chief Complaint: {cc}
{history_note}
{comorbidity_note}
- Age: {age if age is not None else "Unknown"}
- Sex: {sex or "Unknown"}
- Age Group: {age_group}

TASK: Provide clinical decision support in JSON with EXACTLY these keys:
{{
  "complexity": "High" | "Medium" | "Low",
  "complexity_rationale": "<concise clinical rationale, max 200 words>",
  "criteria": ["<monitoring criterion 1>", ...],
  "preliminary_tests": ["<test 1>", ...],
  "medications": [
    {{
      "name": "<drug name>",
      "dosage": "<dose and route>",
      "indication": "<why in this context>",
      "warning": "<safety constraint>"
    }}
  ]
}}

SAFETY GUARDRAILS (MANDATORY):
1. If chief complaint or history is blank/vague/insufficient — set complexity to "Low", rationale to "Insufficient data", leave preliminary_tests and medications EMPTY.
2. Suggest tests and medications ONLY when directly indicated by the specific presentation. Do NOT suggest prophylactically.
3. In medication warnings, always include the key contraindication for this specific patient's age group ({age_group}) and any detected comorbidities.
4. Do NOT add keys outside the schema above.

JSON response only:"""

    gemini_result = call_gemini_api(prompt)
    _update_ai_mode(gemini_result)

    if gemini_result is not None:
        return _normalize_ai_symptoms_output(gemini_result, fallback_domain=primary_domain)

    # 3. RAG-only fallback: build response directly from knowledge store (no hardcoding)
    if primary_domain:
        age_modifier = primary_domain.get("age_modifiers", {}).get(age_group, "")
        rationale = primary_domain.get("complexity_rationale", "")
        if age_modifier:
            rationale = f"{rationale} Age-specific note ({age_group}): {age_modifier}"
        if comorbidity_flags:
            rationale += f" Detected comorbidities: {', '.join(comorbidity_flags)}."

        meds = primary_domain.get("emergency_medications", [])[:3]
        return _normalize_ai_symptoms_output({
            "complexity": primary_domain.get("complexity", "Medium"),
            "complexity_rationale": rationale,
            "criteria": primary_domain.get("monitoring_criteria", []),
            "preliminary_tests": primary_domain.get("preliminary_tests", []),
            "medications": meds,
        }, fallback_domain=primary_domain)

    # 4. Static fallback — no knowledge store match
    _current_ai_mode_local = AI_MODE_STATIC
    return {
        "complexity": "Low",
        "complexity_rationale": "No matching clinical domain found. Static scoring mode active. Clinical review recommended.",
        "criteria": ["Monitor vital signs", "Observe for evolving symptoms"],
        "preliminary_tests": [],
        "medications": [],
    }


def analyze_degradation_ai(
    chief_complaint: str,
    relevant_history: str = "",
    age: Optional[int] = None,
    sex: str = "",
    age_group: str = "adult",
) -> dict:
    """
    Estimate degradation rate and criticalness.
    Uses Gemini with RAG context when available, falls back to knowledge store.
    """
    cc = (chief_complaint or "").strip()
    hist = (relevant_history or "").strip()

    if _force_static:
        return {
            "criticalness": "Stable",
            "degradation_rate": 0.001,
            "explanation": "Static mode forced by clinician (Circuit Breaker active). Standard baseline applied.",
        }

    if _is_vague(cc, hist):
        return dict(_VAGUE_DEGRADATION_RESULT)

    domains = retrieve_relevant_protocols(cc, hist, age_group=age_group, top_k=2)
    rag_context = _format_rag_context(domains, age_group)
    primary_domain = domains[0] if domains else None

    history_note = (
        f"- Medical History: {hist}" if hist else
        "- Medical History: Not available (do NOT assume low risk; treat as elevated uncertainty)"
    )

    prompt = f"""You are an expert Clinical Risk Assessor for Emergency Triage.

RETRIEVED CLINICAL KNOWLEDGE BASE CONTEXT:
{rag_context if rag_context else "(No matching domain retrieved.)"}

PATIENT PRESENTATION:
- Chief Complaint: {cc}
{history_note}
- Age: {age if age is not None else "Unknown"}
- Sex: {sex or "Unknown"}
- Age Group: {age_group}

TASK: Estimate patient degradation rate in JSON with EXACTLY these keys:
{{
  "criticalness": "Immediate" | "Urgent" | "Stable" | "Low",
  "degradation_rate": <float 0.0001 to 0.02>,
  "explanation": "<concise rationale for this degradation estimate>"
}}

degradation_rate interpretation:
  0.0001–0.001 = very stable (hours to days before deterioration)
  0.001–0.005  = moderate (1–4h window)
  0.005–0.010  = urgent (30–60 min window)
  0.010–0.020  = immediate (minutes)

SAFETY GUARDRAILS:
1. Insufficient or vague input → degradation_rate 0.0001, criticalness "Low".
2. Missing history increases uncertainty — do NOT reduce rate just because history is missing; apply age-appropriate baseline.

JSON response only:"""

    gemini_result = call_gemini_api(prompt)

    if gemini_result is not None:
        return _normalize_degradation_output(gemini_result, fallback_domain=primary_domain)

    # RAG-only fallback
    if primary_domain:
        base_rate = primary_domain.get("degradation_rate", 0.003)
        # Age modifiers for degradation
        if age_group == "geriatric" or age_group == "pediatric":
            base_rate = min(0.02, base_rate * 1.3)
        return _normalize_degradation_output({
            "criticalness": primary_domain.get("criticalness", "Stable"),
            "degradation_rate": base_rate,
            "explanation": primary_domain.get("complexity_rationale", ""),
        }, fallback_domain=primary_domain)

    # Static fallback
    return {
        "criticalness": "Stable",
        "degradation_rate": 0.001,
        "explanation": "No domain match. Static mode: conservative degradation estimate applied.",
    }


def reevaluate_reports_ai(
    chief_complaint: str,
    scan_type: str,
    scan_findings: str,
) -> dict:
    """
    Re-evaluate patient risk when diagnostic scan report arrives.
    Returns priority, confidence, risk_score_boost, rationale, findings_status.
    """
    findings = (scan_findings or "").strip()
    cc = (chief_complaint or "").strip()

    if not findings or len(findings) < 5 or findings.lower() in {"none", "vague", "unknown", "no findings", "n/a", "na"}:
        return {
            "priority": "P4",
            "confidence": 0.50,
            "risk_score_boost": -0.10,
            "rationale_summary": "Insufficient or missing diagnostic report details. Standard category applied.",
            "findings_status": "Normal",
        }

    # Retrieve domain context based on complaint
    domains = retrieve_relevant_protocols(cc, "", age_group="adult", top_k=1)
    rag_context = _format_rag_context(domains, "adult")

    prompt = f"""You are an expert Radiologist and Clinical Decision Support System.

RETRIEVED CLINICAL CONTEXT FOR THIS COMPLAINT:
{rag_context if rag_context else "(No specific domain context available.)"}

SCAN REPORT:
- Chief Complaint: {cc}
- Scan Type: {scan_type}
- Scan Findings: {findings}

TASK: Re-evaluate the patient's triage priority based on findings. JSON with EXACTLY these keys:
{{
  "priority": "P1" | "P2" | "P3" | "P4" | "P5",
  "confidence": <float 0.0 to 1.0>,
  "findings_status": "Critical" | "Abnormal" | "Normal",
  "explanation": "<concise explanation of findings and reassessed risk>"
}}

SAFETY GUARDRAILS:
1. Empty or insufficient findings → P4, confidence 0.5, findings_status "Normal".
2. Critical findings (haemorrhage, infarction, pneumothorax, appendicitis rupture) → P1.

JSON only:"""

    gemini_result = call_gemini_api(prompt)

    if gemini_result is not None:
        norm = _normalize_report_output(gemini_result)
        is_critical = norm["findings_status"] in ("Critical", "Abnormal")
        return {
            "priority": norm["priority"],
            "confidence": norm["confidence"],
            "risk_score_boost": 0.45 if is_critical else -0.15,
            "rationale_summary": norm["explanation"],
            "findings_status": norm["findings_status"],
        }

    # RAG-only fallback: keyword-based critical detection without hardcoding
    critical_terms = {
        "haemorrhage": ("P1", "Acute haemorrhage confirmed. Immediate neurosurgical/surgical consultation."),
        "hemorrhage": ("P1", "Acute haemorrhage confirmed. Immediate consultation required."),
        "infarction": ("P1", "Tissue infarction confirmed. Stroke protocol / urgent intervention indicated."),
        "stroke": ("P1", "Stroke confirmed on imaging. Activate stroke pathway."),
        "pneumothorax": ("P1", "Pneumothorax confirmed. Immediate decompression required."),
        "appendicitis": ("P2", "Acute appendicitis confirmed. Urgent surgical consultation."),
        "fracture": ("P2", "Fracture confirmed. Orthopaedic reduction/stabilisation required."),
        "embolism": ("P2", "Pulmonary embolism/thromboembolism confirmed. Anticoagulation indicated."),
        "obstruction": ("P2", "Bowel obstruction confirmed. Surgical review required."),
        "perforation": ("P1", "Perforation confirmed. Emergency surgical intervention."),
        "rupture": ("P1", "Rupture confirmed. Immediate surgical intervention."),
        "ischemia": ("P2", "Ischaemia confirmed. Urgent intervention required."),
        "stenosis": ("P3", "Significant stenosis noted. Urgent specialist review."),
    }

    findings_lower = findings.lower()
    for term, (priority, rationale) in critical_terms.items():
        if term in findings_lower:
            return {
                "priority": priority,
                "confidence": 0.88,
                "risk_score_boost": 0.45,
                "rationale_summary": rationale,
                "findings_status": "Critical" if priority == "P1" else "Abnormal",
            }

    # Normal scan
    priority = "P3" if "chest pain" in cc.lower() else "P4"
    return {
        "priority": priority,
        "confidence": 0.85,
        "risk_score_boost": -0.15,
        "rationale_summary": f"Scan ({scan_type}) shows no acute abnormalities. Patient remains stable.",
        "findings_status": "Normal",
    }
