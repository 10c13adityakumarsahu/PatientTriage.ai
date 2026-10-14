"""Clinician Override views."""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from patients.models import Patient
from .models import ClinicianOverride
from .serializers import ClinicianOverrideSerializer
from audit.models import AuditEvent


@api_view(['POST'])
def create_override(request, patient_id):
    """POST /patients/{patient_id}/override/ — Clinician overrides AI recommendation."""
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

    override_priority = request.data.get('override_priority')
    reason_code = request.data.get('reason_code')

    if not override_priority or not reason_code:
        return Response(
            {'error': 'override_priority and reason_code are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    original_priority = patient.current_priority
    original_destination = patient.current_destination

    override = ClinicianOverride.objects.create(
        patient=patient,
        original_priority=original_priority or 'P3',
        override_priority=override_priority,
        original_destination=original_destination or '',
        override_destination=request.data.get('override_destination', ''),
        reason_code=reason_code,
        note=request.data.get('note', ''),
        clinician_id=request.data.get('clinician_id', 'clinician-1'),
    )

    # Apply override to patient
    patient.current_priority = override_priority
    if override.override_destination:
        patient.current_destination = override.override_destination
        patient.current_queue = override.override_destination
    patient.save(update_fields=['current_priority', 'current_destination', 'current_queue', 'updated_at'])

    # Audit — must be captured for every override
    AuditEvent.log(
        event_type='recommendation_overridden',
        actor_type='clinician',
        actor_id=override.clinician_id,
        patient_id=patient.id,
        old_state={'priority': original_priority, 'destination': original_destination},
        new_state={
            'priority': override_priority,
            'destination': override.override_destination,
            'reason': reason_code,
            'note': override.note,
        },
        trigger='clinician_override',
    )

    # Broadcast
    from simulation.broadcast import broadcast_event
    broadcast_event('priority.changed', {
        'patient_id': str(patient.id),
        'old_priority': original_priority,
        'new_priority': override_priority,
        'actor': 'clinician',
        'reason': reason_code,
    })

    return Response(ClinicianOverrideSerializer(override).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def override_list(request):
    from .serializers import ClinicianOverrideSerializer
    overrides = ClinicianOverride.objects.select_related('patient').all()
    return Response(ClinicianOverrideSerializer(overrides, many=True).data)
