"""Queue views."""
from rest_framework.decorators import api_view
from rest_framework.response import Response

from patients.models import Patient, PatientStatus
from .serializers import LiveQueuePatientSerializer


PRIORITY_ORDER = {'P1': 1, 'P2': 2, 'P3': 3, 'P4': 4, 'P5': 5, None: 9}


@api_view(['GET'])
def live_queue(request):
    """GET /queues/live/ — Returns all active (waiting/in-progress) patients sorted by priority."""
    patients = Patient.objects.filter(
        status__in=[PatientStatus.WAITING, PatientStatus.IN_PROGRESS]
    ).prefetch_related('assessments', 'vital_readings', 'alerts', 'overrides')

    # Sort by priority then wait time
    patients_list = list(patients)
    patients_list.sort(key=lambda p: (
        PRIORITY_ORDER.get(p.current_priority, 9),
        p.arrival_time or ''
    ))

    serializer = LiveQueuePatientSerializer(patients_list, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def queue_stats(request):
    """GET /queues/stats/ — Summary statistics."""
    from patients.models import PatientStatus
    from django.utils import timezone

    waiting = Patient.objects.filter(status=PatientStatus.WAITING)
    total = waiting.count()

    by_priority = {}
    for p in ['P1', 'P2', 'P3', 'P4', 'P5']:
        by_priority[p] = waiting.filter(current_priority=p).count()

    # Escalating = patients with active critical/warning alerts
    from alerts.models import Alert, AlertSeverity
    escalating_ids = set(
        Alert.objects.filter(acknowledged_at__isnull=True, severity=AlertSeverity.CRITICAL)
        .values_list('patient_id', flat=True)
    )

    # Calculate average resource utilization from resources
    try:
        from routing.models import Resource
        resources = Resource.objects.all()
        total_capacity = sum(r.capacity for r in resources)
        total_occupied = sum(r.occupied for r in resources)
        avg_utilisation = (total_occupied / total_capacity * 100) if total_capacity else 0
    except Exception:
        avg_utilisation = 0

    return Response({
        'total_waiting': total,
        'by_priority': by_priority,
        'p1_p2_count': by_priority['P1'] + by_priority['P2'],
        'escalating_count': len(escalating_ids),
        'average_resource_utilisation': avg_utilisation,
        'timestamp': timezone.now().isoformat(),
    })


@api_view(['POST'])
def recompute_queue(request):
    """POST /queues/recompute/ — Trigger reassessment for all waiting patients."""
    from triage.services import run_triage_assessment
    from patients.models import PatientStatus

    patients = Patient.objects.filter(status=PatientStatus.WAITING)
    count = 0
    for patient in patients:
        run_triage_assessment(patient, trigger='queue_recompute')
        count += 1

    return Response({'recomputed': count})
