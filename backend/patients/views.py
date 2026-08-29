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
    patient.save()

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
        })

    return Response({
        'exists': True,
        'demographics': {
            'name': latest.name,
            'age': latest.age,
            'sex': latest.sex,
            'relevant_history': latest.relevant_history,
        },
        'past_records': past_records
    })
