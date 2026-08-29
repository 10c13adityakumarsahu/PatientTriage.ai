"""Simulation views — seed, tick, surge, reset."""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone

from .seeder import seed_baseline, trigger_deterioration, trigger_surge, reset_simulation
from .models import SimulationState
from patients.models import Patient
from triage.services import run_triage_assessment
from audit.models import AuditEvent


@api_view(['POST'])
def seed(request):
    """POST /simulation/seed/ — Initialize baseline scenario."""
    patients = seed_baseline()
    return Response({
        'message': f'Baseline scenario seeded with {len(patients)} patients',
        'patient_count': len(patients),
    })


@api_view(['POST'])
def tick(request):
    """POST /simulation/tick/ — Advance simulation clock and reassess waiting patients."""
    from datetime import timedelta
    from simulation.broadcast import broadcast_event

    minutes = int(request.data.get('minutes', 5))

    state = SimulationState.objects.first()
    if not state:
        state = SimulationState.objects.create(
            scenario_name='baseline',
            surge_active=False,
            sim_time=timezone.now(),
            is_running=True
        )
    else:
        state.sim_time += timedelta(minutes=minutes)
        state.save()

    waiting = Patient.objects.filter(status='waiting')
    reassessed = 0

    for patient in waiting:
        # Check if past reassessment threshold
        from decision_engine.age_profiles import get_wait_threshold
        if patient.arrival_time:
            wait_min = int((state.sim_time - patient.arrival_time).total_seconds() / 60)
            threshold = get_wait_threshold(patient.age_group, patient.current_priority or 'P4')
            if threshold > 0 and wait_min >= threshold:
                run_triage_assessment(patient, trigger='wait_threshold_reached')
                reassessed += 1

    # Broadcast simulation event so frontend automatically refreshes
    broadcast_event('simulation.reset', {'tick': True, 'sim_time': str(state.sim_time)})

    return Response({'message': f'Tick +{minutes}m, reassessed {reassessed} patients'})


@api_view(['POST'])
def deteriorate(request):
    """POST /simulation/deteriorate/ — Trigger deterioration for a patient."""
    patient_id = request.data.get('patient_id')
    if not patient_id:
        return Response({'error': 'patient_id required'}, status=status.HTTP_400_BAD_REQUEST)

    assessment = trigger_deterioration(patient_id)
    if not assessment:
        return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

    from triage.serializers import RiskAssessmentSerializer
    return Response(RiskAssessmentSerializer(assessment).data)


@api_view(['POST'])
def surge(request):
    """POST /simulation/surge/ — Activate 3× surge."""
    patients = trigger_surge()
    return Response({
        'message': f'Surge activated. Added {len(patients)} patients.',
        'surge_active': True,
    })


@api_view(['POST'])
def reset(request):
    """POST /simulation/reset/ — Reset simulation to clean state."""
    reset_simulation()
    return Response({'message': 'Simulation reset', 'reset': True})


@api_view(['GET'])
def sim_status(request):
    """GET /simulation/status/ — Current simulation state."""
    state = SimulationState.objects.first()
    if state:
        return Response({
            'scenario': state.scenario_name,
            'surge_active': state.surge_active,
            'is_running': state.is_running,
            'sim_time': state.sim_time,
        })
    return Response({'running': False, 'surge_active': False})
