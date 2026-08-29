"""Audit views."""
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = [
            'id', 'patient_id', 'actor_type', 'actor_id',
            'event_type', 'old_state', 'new_state',
            'trigger', 'confidence', 'created_at'
        ]


@api_view(['GET'])
def audit_list(request):
    patient_id = request.query_params.get('patient_id')
    event_type = request.query_params.get('event_type')
    qs = AuditEvent.objects.all()
    if patient_id:
        qs = qs.filter(patient_id=patient_id)
    if event_type:
        qs = qs.filter(event_type=event_type)
    qs = qs[:200]  # limit for prototype
    return Response(AuditEventSerializer(qs, many=True).data)
