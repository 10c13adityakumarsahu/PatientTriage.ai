"""
Pure Python data models for the Decision Engine.
No Django ORM coupling — fully testable in isolation.
"""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class VitalSnapshot:
    heart_rate: Optional[float] = None
    systolic_bp: Optional[float] = None
    diastolic_bp: Optional[float] = None
    spo2: Optional[float] = None
    respiratory_rate: Optional[float] = None
    temperature: Optional[float] = None
    mental_status: str = "alert"  # alert | confused | unresponsive
    recorded_at: Optional[datetime] = None


@dataclass
class PatientState:
    """Complete patient state fed into the decision engine."""
    patient_id: str
    age: int
    age_group: str          # pediatric | adult | geriatric
    chief_complaint: str
    symptoms: list = field(default_factory=list)       # normalized symptom tokens
    history_available: bool = True
    relevant_history: str = ""
    observed_cues: list = field(default_factory=list)
    current_vitals: Optional[VitalSnapshot] = None
    previous_vitals: Optional[VitalSnapshot] = None    # for trend detection
    current_priority: Optional[str] = None
    waiting_minutes: int = 0
    prior_assessments_count: int = 0
    conflicting_signals: list = field(default_factory=list)
    missing_fields: list = field(default_factory=list)
    clinician_overridden: bool = False
    scenario_tag: str = ""


@dataclass
class AssessmentResult:
    """Output contract from the decision engine."""
    priority: str                  # P1–P5
    confidence: float              # 0.0–1.0
    confidence_label: str          # high | medium | low
    risk_factors: list             # human-readable top factors
    uncertainty_flags: list        # human-readable flags
    missing_fields: list
    recommended_action: str
    recommended_destination: str
    requires_human_review: bool
    safety_state: str              # GREEN | YELLOW | RED
    model_version: str = "rule-engine-v1"
    raw_score: float = 0.0
