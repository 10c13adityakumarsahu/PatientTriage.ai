"""Alerts serializers and views."""
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone

from .models import Alert


class AlertSerializer(serializers.ModelSerializer):
    is_active = serializers.ReadOnlyField()
    patient_info = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = [
            'id', 'patient_id', 'patient_info', 'alert_type', 'severity',
            'title', 'message', 'is_active',
            'acknowledged_at', 'acknowledged_by', 'created_at'
        ]

    def get_patient_info(self, obj):
        if obj.patient:
            return {
                'id': str(obj.patient.id),
                'age': obj.patient.age,
                'age_group': obj.patient.age_group,
                'chief_complaint': obj.patient.chief_complaint,
                'current_priority': obj.patient.current_priority,
            }
        return None


@api_view(['GET'])
def alert_list(request):
    active_param = request.query_params.get('active')
    qs = Alert.objects.select_related('patient').all()
    if active_param == 'true':
        qs = qs.filter(acknowledged_at__isnull=True)
    return Response(AlertSerializer(qs, many=True).data)


@api_view(['POST'])
def acknowledge_alert(request, alert_id):
    try:
        alert = Alert.objects.get(id=alert_id)
    except Alert.DoesNotExist:
        return Response({'error': 'Alert not found'}, status=status.HTTP_404_NOT_FOUND)

    alert.acknowledged_at = timezone.now()
    alert.acknowledged_by = request.data.get('acknowledged_by', 'clinician-1')
    alert.save()

    from audit.models import AuditEvent
    AuditEvent.log(
        event_type='alert_acknowledged',
        actor_type='clinician',
        actor_id=alert.acknowledged_by,
        patient_id=alert.patient_id,
        old_state={'acknowledged': False},
        new_state={'acknowledged': True, 'by': alert.acknowledged_by},
        trigger='clinician_action',
    )

    return Response(AlertSerializer(alert).data)
