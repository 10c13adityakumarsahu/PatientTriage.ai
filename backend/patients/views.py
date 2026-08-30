"""Patient views — REST API endpoints."""
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Patient, VitalReading, PatientNote
from .serializers import (
    PatientListSerializer, PatientDetailSerializer,
    PatientCreateSerializer, VitalReadingSerializer, PatientNoteSerializer
)
from audit.models import AuditEvent
from decision_engine.normalizer import normalize_symptoms


@api_view(['GET', 'POST'])
def patient_list_create(request):
    if request.method == 'GET':
        status_filter = request.query_params.get('status')
        qs = Patient.objects.all()
        if status_filter:
            qs = qs.filter(status=status_filter)
        serializer = PatientListSerializer(qs, many=True)
        return Response(serializer.data)

    # POST — create patient
    ser = PatientCreateSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    patient = ser.save()

    # Normalize symptoms from chief complaint
    tokens, flags = normalize_symptoms(patient.chief_complaint)
    if tokens:
        PatientNote.objects.create(
            patient=patient,
            raw_text=patient.chief_complaint,
            normalized_symptoms=tokens,
            extracted_flags=flags,
            source='intake'
        )

    AuditEvent.log(
        event_type='patient_created',
        actor_type='system',
        patient_id=patient.id,
        new_state={'priority': None, 'status': patient.status},
        trigger='patient_registration',
    )

    from simulation.broadcast import broadcast_event
    broadcast_event('patient.created', PatientListSerializer(patient).data)

    return Response(PatientDetailSerializer(patient).data, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH'])
def patient_detail(request, patient_id):
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(PatientDetailSerializer(patient).data)

    # PATCH — update patient fields
    old_id = patient.patient_identifier
    old_doctor = patient.assigned_doctor
    old_status = patient.status

    patient.status = request.data.get('status', patient.status)
    patient.name = request.data.get('name', patient.name)
    patient.patient_identifier = request.data.get('patient_identifier', patient.patient_identifier)
    
    if 'age' in request.data:
        try:
            patient.age = int(request.data['age'])
            patient.age_group = patient.get_age_group()
        except (ValueError, TypeError):
            pass
            
    patient.sex = request.data.get('sex', patient.sex)
    patient.relevant_history = request.data.get('relevant_history', patient.relevant_history)
    patient.assigned_doctor = request.data.get('assigned_doctor', patient.assigned_doctor)

    # Set last_attended_time if assigned doctor or status changed to in_progress
    from simulation.models import SimulationState
    from django.utils import timezone
    sim_state = SimulationState.objects.first()
    current_time = sim_state.sim_time if (sim_state and sim_state.is_running and sim_state.sim_time) else timezone.now()

    if (patient.assigned_doctor and patient.assigned_doctor != old_doctor) or (patient.status == 'in_progress' and old_status != 'in_progress'):
        patient.last_attended_time = current_time

    # Dynamic sequence and logic for dispositions (Admit / Refer / Discharge)
    if patient.status != old_status and patient.status in ['admitted', 'referred', 'discharged']:
        if patient.status == 'admitted':
            # Admit sequence: patient is moved to observation bed, priority changed to P5
            patient.current_priority = 'P5'
            patient.dynamic_priority_score = 0.0
            patient.assigned_doctor = None  # Free up ED doctor
            patient.under_scan = False
        else:
            # Discharge / Refer sequence: patient leaves ED, priority cleared, resources freed
            patient.current_priority = None
            patient.dynamic_priority_score = 0.0
            patient.assigned_doctor = None
            patient.under_scan = False

    patient.save()

    # Recalculate resource utilization
    from routing.scheduler import recalculate_resource_occupancy
    recalculate_resource_occupancy()

    # If identifier changed and is resolved, run reassessment to incorporate history
    id_changed = (old_id != patient.patient_identifier)
    if id_changed:
        from triage.services import run_triage_assessment
        run_triage_assessment(patient, trigger='identity_resolved')
        
        AuditEvent.log(
            event_type='patient_updated',
            actor_type='clinician',
            actor_id='clinician-1',
            patient_id=patient.id,
            new_state={
                'patient_identifier': patient.patient_identifier,
                'name': patient.name,
                'age': patient.age,
                'relevant_history': patient.relevant_history,
            },
            trigger='identity_resolution',
        )

    return Response(PatientDetailSerializer(patient).data)


@api_view(['POST'])
def add_vitals(request, patient_id):
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

    data = request.data.copy()
    if 'recorded_at' not in data:
        data['recorded_at'] = timezone.now().isoformat()

    ser = VitalReadingSerializer(data=data)
    if not ser.is_valid():
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)

    vitals = ser.save(patient=patient)

    AuditEvent.log(
        event_type='vitals_recorded',
        actor_type='system',
        patient_id=patient.id,
        new_state=ser.data,
        trigger='vital_update',
    )

    from simulation.broadcast import broadcast_event
    broadcast_event('patient.updated', {'patient_id': str(patient.id), 'type': 'vitals'})

    return Response(ser.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def add_observation(request, patient_id):
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

    raw_text = request.data.get('raw_text', '')
    tokens, flags = normalize_symptoms(raw_text)

    note = PatientNote.objects.create(
        patient=patient,
        raw_text=raw_text,
        normalized_symptoms=tokens,
        extracted_flags=flags,
        source=request.data.get('source', 'nurse'),
    )

    return Response(PatientNoteSerializer(note).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def patient_lookup(request):
    """GET /patients/lookup/ — lookup demographics and past records."""
    identifier = request.query_params.get('identifier')
    if not identifier:
        return Response({'error': 'identifier query param required'}, status=status.HTTP_400_BAD_REQUEST)

    # Search for patients with this identifier, order by most recent arrival
    matches = Patient.objects.filter(patient_identifier=identifier).order_by('-arrival_time')
    if not matches.exists():
        return Response({'exists': False}, status=status.HTTP_200_OK)

    # Demographic data from latest record
    latest = matches.first()
    
    # Compile past visit records
    past_records = []
    for p in matches:
        assessments_data = []
        for a in p.assessments.all():
            assessments_data.append({
                'id': str(a.id),
                'priority': a.priority,
                'confidence': a.confidence,
                'recommended_destination': a.recommended_destination,
                'created_at': a.created_at.isoformat(),
            })
            
        latest_vitals = p.vital_readings.order_by('-recorded_at').first()
        vitals_data = None
        if latest_vitals:
            vitals_data = {
                'heart_rate': latest_vitals.heart_rate,
                'spo2': latest_vitals.spo2,
                'respiratory_rate': latest_vitals.respiratory_rate,
                'systolic_bp': latest_vitals.systolic_bp,
                'diastolic_bp': latest_vitals.diastolic_bp,
                'temperature': latest_vitals.temperature,
                'mental_status': latest_vitals.mental_status,
                'recorded_at': latest_vitals.recorded_at.isoformat(),
            }

        past_records.append({
            'patient_id': str(p.id),
            'arrival_time': p.arrival_time.isoformat(),
            'chief_complaint': p.chief_complaint,
            'current_priority': p.current_priority,
            'status': p.status,
            'latest_vitals': vitals_data,
            'assessments': assessments_data,
            'assigned_doctor': p.assigned_doctor,
        })

    return Response({
        'exists': True,
        'demographics': {
            'name': latest.name,
            'age': latest.age,
            'sex': latest.sex,
            'relevant_history': latest.relevant_history,
            'assigned_doctor': latest.assigned_doctor,
        },
        'past_records': past_records
    })


@api_view(['POST'])
def mark_under_scan(request, patient_id):
    """POST /patients/<id>/mark-under-scan/ — Marks patient as currently undergoing scan (blocks from CPU/doctor scheduling)"""
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

    from simulation.models import SimulationState
    from django.utils import timezone
    sim_state = SimulationState.objects.first()
    current_time = sim_state.sim_time if (sim_state and sim_state.is_running and sim_state.sim_time) else timezone.now()

    patient.under_scan = True
    patient.scheduler_state = 'blocked'
    patient.dynamic_priority_score = 0.0
    patient.last_attended_time = current_time
    patient.save(update_fields=['under_scan', 'scheduler_state', 'dynamic_priority_score', 'last_attended_time'])

    from routing.scheduler import recalculate_resource_occupancy
    recalculate_resource_occupancy()

    AuditEvent.log(
        event_type='scan_initiated',
        actor_type='clinician',
        actor_id='clinician-1',
        patient_id=patient.id,
        new_state={'under_scan': True, 'scheduler_state': 'blocked'},
        trigger='manual_scan_order'
    )

    from simulation.broadcast import broadcast_event
    broadcast_event('patient.updated', {'patient_id': str(patient.id), 'type': 'scan_started'})

    from patients.serializers import PatientDetailSerializer
    return Response(PatientDetailSerializer(patient).data)


@api_view(['POST'])
def submit_scan_reports(request, patient_id):
    """POST /patients/<id>/submit-scan-reports/ — Manual scan reports submission, triggers AI re-evaluation"""
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

    scan_findings = request.data.get('scan_findings', '')
    scan_type = request.data.get('scan_type', 'Diagnostic Scan')
    skip_report = request.data.get('skip_report', False)

    from simulation.models import SimulationState
    from django.utils import timezone
    sim_state = SimulationState.objects.first()
    current_time = sim_state.sim_time if (sim_state and sim_state.is_running and sim_state.sim_time) else timezone.now()

    patient.under_scan = False
    patient.scheduler_state = 'ready'
    patient.last_attended_time = current_time

    old_priority = patient.current_priority

    if skip_report:
        new_priority = patient.current_priority or "P4"
        scan_findings = "No report uploaded (skipped by clinician)."
        patient.scan_reports = scan_findings
        ai_res = {
            "priority": new_priority,
            "confidence": 1.0,
            "findings_status": "Normal",
            "explanation": "Scan completed without report upload."
        }
    else:
        if not scan_findings:
            # Generate default reports based on chief complaint if not provided
            from routing.scheduler import generate_simulated_report
            scan_findings = generate_simulated_report(patient.chief_complaint, patient.scenario_tag)

        patient.scan_reports = scan_findings

        # Trigger AI report re-evaluation
        from decision_engine.ai_assistant import reevaluate_reports_ai
        ai_res = reevaluate_reports_ai(patient.chief_complaint, scan_type, scan_findings)
        new_priority = ai_res.get("priority", "P4")

    patient.current_priority = new_priority
    patient.current_destination = "general_emergency" if ai_res.get("confidence", 1.0) < 0.60 else (patient.current_destination or "general_emergency")
    patient.current_queue = patient.current_destination
    
    # Calculate boost and dynamic priority score
    prio_base = {"P1": 0.90, "P2": 0.70, "P3": 0.50, "P4": 0.30, "P5": 0.10}
    base_score = prio_base.get(new_priority, 0.10)
    
    # Add unblocked boost
    patient.dynamic_priority_score = min(2.0, base_score + 0.25)
    patient.save(update_fields=['under_scan', 'scheduler_state', 'scan_reports', 'current_priority', 'current_destination', 'current_queue', 'dynamic_priority_score', 'last_attended_time'])

    from routing.scheduler import recalculate_resource_occupancy
    recalculate_resource_occupancy()

    # Log audit event
    AuditEvent.log(
        event_type='scan_completed',
        actor_type='clinician',
        actor_id='clinician-1',
        patient_id=patient.id,
        old_state={'priority': old_priority, 'under_scan': True},
        new_state={
            'priority': new_priority, 
            'under_scan': False, 
            'scan_reports': scan_findings[:100] + "...",
            'findings_status': ai_res.get("findings_status")
        },
        trigger='manual_scan_completion',
        confidence=ai_res.get("confidence", 0.90)
    )

    # Re-create QueueEntry
    from django.utils import timezone
    from queues.models import QueueEntry
    QueueEntry.objects.filter(patient=patient, active=True).update(active=False, exited_at=timezone.now())
    QueueEntry.objects.create(
        patient=patient,
        queue_type=patient.current_queue or "general_emergency",
        priority=new_priority,
        active=True
    )

    from simulation.broadcast import broadcast_event
    broadcast_event('patient.updated', {'patient_id': str(patient.id), 'type': 'scan_completed'})

    from patients.serializers import PatientDetailSerializer
    return Response(PatientDetailSerializer(patient).data)
