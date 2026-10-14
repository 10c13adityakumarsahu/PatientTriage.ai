"""Override serializers and views."""
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import ClinicianOverride
from patients.models import Patient
from audit.models import AuditEvent


class ClinicianOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicianOverride
        fields = [
            'id', 'patient_id', 'original_priority', 'override_priority',
            'original_destination', 'override_destination',
            'reason_code', 'note', 'clinician_id', 'created_at'
        ]


@api_view(['GET'])
def override_list(request):
    overrides = ClinicianOverride.objects.select_related('patient').all()
    return Response(ClinicianOverrideSerializer(overrides, many=True).data)
