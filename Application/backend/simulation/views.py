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
    """POST /simulation/tick/ — Advance simulation clock or step through scheduler stages."""
    from datetime import timedelta
    from simulation.broadcast import broadcast_event
    from routing.scheduler import run_scheduler_cycle

    step_mode = request.data.get('step', False)
    if isinstance(step_mode, str):
        step_mode = step_mode.lower() == 'true'

    state = SimulationState.objects.first()
    if not state:
        state = SimulationState.objects.create(
            scenario_name='baseline',
            surge_active=False,
            sim_time=timezone.now(),
            is_running=True,
            current_stage='wait_reassessment'
        )

    minutes = int(request.data.get('minutes', 5))
    reassessed = 0

    if step_mode:
        active_stage = state.current_stage or 'wait_reassessment'
        
        if active_stage == 'wait_reassessment':
            # Advance clock only at start of the stage cycle
            state.sim_time += timedelta(minutes=minutes)
            state.save()
            
            # Gradually populate vitals
            from .seeder import simulate_gradual_flow
            simulate_gradual_flow(state.sim_time)
            
            waiting = Patient.objects.filter(status='waiting')
            for patient in waiting:
                from decision_engine.age_profiles import get_wait_threshold
                if patient.arrival_time:
                    wait_min = int((state.sim_time - patient.arrival_time).total_seconds() / 60)
                    threshold = get_wait_threshold(patient.age_group, patient.current_priority or 'P4')
                    if threshold > 0 and wait_min >= threshold:
                        run_triage_assessment(patient, trigger='wait_threshold_reached')
                        reassessed += 1
            next_stage = 'io_completion'
        elif active_stage == 'io_completion':
            run_scheduler_cycle(stage='io_completion')
            next_stage = 'priority_aging'
        elif active_stage == 'priority_aging':
            run_scheduler_cycle(stage='priority_aging')
            next_stage = 'core_allocation'
        else: # core_allocation
            run_scheduler_cycle(stage='core_allocation')
            next_stage = 'wait_reassessment'

        state.current_stage = next_stage
        state.save()
        
        # Broadcast simulation state update
        broadcast_event('simulation.reset', {
            'tick': True, 
            'sim_time': str(state.sim_time),
            'stage_executed': active_stage,
            'next_stage': next_stage,
            'step_mode': True
        })
        
        return Response({
            'message': f'Executed simulation stage: {active_stage}',
            'stage_executed': active_stage,
            'next_stage': next_stage,
            'reassessed_count': reassessed,
            'sim_time': str(state.sim_time)
        })
    else:
        # Full cycle tick
        state.sim_time += timedelta(minutes=minutes)
        state.current_stage = 'wait_reassessment'
        state.save()

        # Gradually populate vitals
        from .seeder import simulate_gradual_flow
        simulate_gradual_flow(state.sim_time)

        waiting = Patient.objects.filter(status='waiting')
        for patient in waiting:
            from decision_engine.age_profiles import get_wait_threshold
            if patient.arrival_time:
                wait_min = int((state.sim_time - patient.arrival_time).total_seconds() / 60)
                threshold = get_wait_threshold(patient.age_group, patient.current_priority or 'P4')
                if threshold > 0 and wait_min >= threshold:
                    run_triage_assessment(patient, trigger='wait_threshold_reached')
                    reassessed += 1

        run_scheduler_cycle(stage=None)
        
        broadcast_event('simulation.reset', {
            'tick': True, 
            'sim_time': str(state.sim_time),
            'step_mode': False
        })
        
        return Response({
            'message': f'Full tick +{minutes}m, reassessed {reassessed} patients',
            'sim_time': str(state.sim_time)
        })


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
    from simulation.models import SimulationState
    sim = SimulationState.objects.first()
    if sim and sim.surge_active:
        return Response({
            'error': 'Surge has already been activated.',
            'surge_active': True,
        }, status=status.HTTP_400_BAD_REQUEST)

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


@api_view(['POST'])
def intake_next(request):
    """POST /simulation/intake-next/ — Seed the next synthetic patient sequentially."""
    from .seeder import intake_next_patient
    patient = intake_next_patient()
    if patient:
        return Response({
            'message': f'Simulated patient intake: {patient.name} ({patient.chief_complaint})',
            'patient_added': True,
            'name': patient.name,
        }, status=status.HTTP_201_CREATED)
    return Response({
        'message': 'All 20 synthetic patients have already been seeded.',
        'patient_added': False,
    }, status=status.HTTP_200_OK)


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
            'current_stage': state.current_stage,
        })
    return Response({'running': False, 'surge_active': False})


@api_view(['GET'])
def next_patient_data(request):
    """GET /simulation/next-patient-data/ — Get demographics for next unsaved synthetic patient."""
    from .seeder import get_next_patient_intake_data
    data = get_next_patient_intake_data()
    if data:
        return Response(data)
    return Response({'error': 'All synthetic patients have been registered.'}, status=status.HTTP_404_NOT_FOUND)
