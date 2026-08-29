"""
Main Decision Engine — orchestrates the full assessment pipeline.

Pipeline:
  PatientState → Normalize → Risk Score → Confidence → Safety Guardrails
              → Priority → Routing → AssessmentResult
"""
from .models import PatientState, AssessmentResult
from .risk_scorer import compute_raw_risk
from .confidence_calculator import compute_confidence, confidence_label
from .safety_guardrails import apply_guardrails
from .priority_mapper import score_to_priority, priority_to_action, priority_to_destination
from .routing_engine import recommend_destination
from .explainer import generate_explanation


def assess_patient(state: PatientState, resources: list = None, surge_active: bool = False) -> AssessmentResult:
    """
    Full assessment pipeline. Returns AssessmentResult.
    This is the primary entry point for the decision engine.
    """
    # Step 1: Compute raw risk score and contributing factors
    raw_score, risk_factors = compute_raw_risk(state)

    # Step 2: Map risk score to proposed priority
    proposed_priority = score_to_priority(raw_score)

    # Step 3: Compute confidence
    confidence, uncertainty_flags, missing_fields = compute_confidence(state)

    # Step 4: Apply safety guardrails (may escalate priority)
    final_priority, safety_state, requires_review, safety_note = apply_guardrails(
        state, proposed_priority, confidence, risk_factors, uncertainty_flags
    )

    # Step 5: Routing recommendation
    destination, routing_rationale, routing_confidence = recommend_destination(
        final_priority, resources or [], surge_active
    )

    # Step 6: Recommended action
    action = priority_to_action(final_priority)

    # Step 7: Generate explanation
    explanation = generate_explanation(
        risk_factors, uncertainty_flags, missing_fields,
        final_priority, confidence, safety_note
    )

    # Merge explanation factors into risk_factors for output
    top_factors = explanation["top_factors"]
    conf_label = confidence_label(confidence)

    return AssessmentResult(
        priority=final_priority,
        confidence=confidence,
        confidence_label=conf_label,
        risk_factors=top_factors,
        uncertainty_flags=uncertainty_flags,
        missing_fields=missing_fields,
        recommended_action=action,
        recommended_destination=destination,
        requires_human_review=requires_review,
        safety_state=safety_state,
        raw_score=raw_score,
    )


def reassess_patient(state: PatientState, resources: list = None, surge_active: bool = False) -> AssessmentResult:
    """
    Re-assessment triggered by vital update, time threshold, or deterioration.
    Same pipeline, but context includes prior assessment info.
    """
    return assess_patient(state, resources=resources, surge_active=surge_active)
