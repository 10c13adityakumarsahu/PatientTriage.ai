"""
Triage service — bridges Django ORM data to the pure Decision Engine.
Builds PatientState from Django models and writes AssessmentResult back.
"""
from django.utils import timezone

from patients.models import Patient, VitalReading
from triage.models import RiskAssessment
from queues.models import QueueEntry, QueueType
from routing.models import Resource
from audit.models import AuditEvent

from decision_engine.models import PatientState, VitalSnapshot
from decision_engine.engine import assess_patient, reassess_patient
from decision_engine.normalizer import normalize_symptoms


def _build_vital_snapshot(vital_reading):
    if vital_reading is None:
        return None
    return VitalSnapshot(
        heart_rate=vital_reading.heart_rate,
        systolic_bp=vital_reading.systolic_bp,
        diastolic_bp=vital_reading.diastolic_bp,
        spo2=vital_reading.spo2,
        respiratory_rate=vital_reading.respiratory_rate,
        temperature=vital_reading.temperature,
        mental_status=vital_reading.mental_status,
        recorded_at=vital_reading.recorded_at,
    )


def _build_patient_state(patient, trigger='initial_assessment') -> PatientState:
    """Construct PatientState from Django ORM patient."""
    vitals = patient.vital_readings.order_by('-recorded_at').first()
    previous_vitals = patient.vital_readings.order_by('-recorded_at')[1:2].first()

    # Collect all normalized symptoms across notes
    symptoms = []
    for note in patient.notes.all():
        symptoms.extend(note.normalized_symptoms or [])
    # Also normalize chief complaint
    extra_tokens, _ = normalize_symptoms(patient.chief_complaint)
    for t in extra_tokens:
        if t not in symptoms:
            symptoms.append(t)

    # Wait time
    wait_minutes = 0
    if patient.arrival_time:
        from simulation.models import SimulationState
        sim_state = SimulationState.objects.first()
        current_time = sim_state.sim_time if (sim_state and sim_state.is_running and sim_state.sim_time) else timezone.now()
        delta = current_time - patient.arrival_time
        wait_minutes = int(delta.total_seconds() / 60)

    # Prior assessments
    prior_count = patient.assessments.count()

    return PatientState(
        patient_id=str(patient.id),
        age=patient.age,
        age_group=patient.age_group,
        chief_complaint=patient.chief_complaint,
        symptoms=list(set(symptoms)),
        history_available=patient.history_available,
        relevant_history=patient.relevant_history or '',
        current_vitals=_build_vital_snapshot(vitals),
        previous_vitals=_build_vital_snapshot(previous_vitals),
        current_priority=patient.current_priority,
        waiting_minutes=wait_minutes,
        prior_assessments_count=prior_count,
        clinician_overridden=patient.overrides.exists(),
        scenario_tag=patient.scenario_tag or '',
    )


def _get_resources():
    """Fetch current resource capacity from DB."""
    return [
        {
            'resource_type': r.resource_type,
            'available_slots': r.available_slots,
            'status': r.status,
        }
        for r in Resource.objects.all()
    ]


def _is_surge_active():
    """Check if surge simulation is currently active."""
    from simulation.models import SimulationState
    try:
        state = SimulationState.objects.first()
        return state and state.surge_active
    except Exception:
        return False


def run_triage_assessment(patient, trigger='initial_assessment') -> RiskAssessment:
    """
    Build state, run decision engine, persist result, create audit event.
    Returns the saved RiskAssessment.
    """
    state = _build_patient_state(patient, trigger=trigger)
    resources = _get_resources()
    surge = _is_surge_active()

    if trigger == 'initial_assessment':
        result = assess_patient(state, resources=resources, surge_active=surge)
    else:
        result = reassess_patient(state, resources=resources, surge_active=surge)

    old_priority = patient.current_priority

    # Run AI Assistant clinical assessment
    from decision_engine.ai_assistant import analyze_symptoms_ai
    ai_support = analyze_symptoms_ai(
        chief_complaint=patient.chief_complaint,
        relevant_history=patient.relevant_history or '',
        age=patient.age,
        sex=patient.sex or ''
    )

    # Persist assessment
    assessment = RiskAssessment.objects.create(
        patient=patient,
        priority=result.priority,
        confidence=result.confidence,
        risk_factors=result.risk_factors,
        uncertainty_flags=result.uncertainty_flags,
        missing_fields=result.missing_fields,
        recommended_action=result.recommended_action,
        recommended_destination=result.recommended_destination,
        requires_human_review=result.requires_human_review,
        trigger=trigger,
        ai_decision_support=ai_support,
    )

    # Update patient priority
    priority_changed = patient.current_priority != result.priority
    patient.current_priority = result.priority
    patient.current_destination = result.recommended_destination
    patient.current_queue = result.recommended_destination
    patient.save(update_fields=['current_priority', 'current_destination', 'current_queue', 'updated_at'])

    # Update or create queue entry
    QueueEntry.objects.filter(patient=patient, active=True).update(
        active=False, exited_at=timezone.now()
    )
    QueueEntry.objects.create(
        patient=patient,
        queue_type=result.recommended_destination,
        priority=result.priority,
        active=True,
    )

    # Audit
    event_type = 'priority_changed' if priority_changed else 'assessment_generated'
    AuditEvent.log(
        event_type=event_type,
        actor_type='ai',
        actor_id='decision-engine-v1',
        patient_id=patient.id,
        old_state={'priority': old_priority},
        new_state={'priority': result.priority, 'confidence': result.confidence},
        trigger=trigger,
        confidence=result.confidence,
    )

    # Broadcast if priority changed
    if priority_changed:
        from simulation.broadcast import broadcast_event
        from patients.serializers import PatientListSerializer
        broadcast_event('priority.changed', {
            'patient_id': str(patient.id),
            'old_priority': old_priority,
            'new_priority': result.priority,
            'confidence': result.confidence,
            'requires_human_review': result.requires_human_review,
        })

    # Create alerts if needed
    _maybe_create_alerts(patient, result, state)

    return assessment


def _maybe_create_alerts(patient, result, state):
    """Create alerts based on assessment result."""
    from alerts.models import Alert, AlertType, AlertSeverity
    from simulation.broadcast import broadcast_event

    alerts_created = []

    if result.requires_human_review and result.safety_state == 'RED':
        a = Alert.objects.create(
            patient=patient,
            alert_type=AlertType.DETERIORATION,
            severity=AlertSeverity.CRITICAL,
            title=f"Critical: {patient.chief_complaint[:50]}",
            message=f"Patient {patient.age}y {patient.age_group} requires immediate attention. "
                    f"Priority: {result.priority}. Confidence: {result.confidence:.0%}. "
                    f"Factors: {'; '.join(result.risk_factors[:2])}",
        )
        alerts_created.append(a)

    elif result.requires_human_review and result.safety_state == 'YELLOW':
        a = Alert.objects.create(
            patient=patient,
            alert_type=AlertType.LOW_CONFIDENCE if result.confidence < 0.60 else AlertType.ESCALATION,
            severity=AlertSeverity.WARNING,
            title=f"Review: {patient.chief_complaint[:50]}",
            message=f"Patient {patient.age}y requires clinician review. "
                    f"Confidence: {result.confidence:.0%}. "
                    f"Flags: {'; '.join(result.uncertainty_flags[:2])}",
        )
        alerts_created.append(a)

    if state.waiting_minutes > 0:
        from decision_engine.age_profiles import get_wait_threshold
        threshold = get_wait_threshold(patient.age_group, result.priority)
        if threshold > 0 and state.waiting_minutes >= threshold:
            a = Alert.objects.create(
                patient=patient,
                alert_type=AlertType.WAIT_THRESHOLD,
                severity=AlertSeverity.WARNING,
                title=f"Long wait: {patient.chief_complaint[:40]}",
                message=f"Patient {patient.age}y ({result.priority}) has waited {state.waiting_minutes}m "
                        f"(threshold: {threshold}m).",
            )
            alerts_created.append(a)

    for alert in alerts_created:
        from alerts.serializers import AlertSerializer
        broadcast_event('alert.created', AlertSerializer(alert).data)
