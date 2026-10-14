"""Queue serializers and views."""
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import QueueEntry
from patients.models import Patient
from patients.serializers import PatientListSerializer
from triage.models import RiskAssessment
from triage.serializers import RiskAssessmentSerializer
from django.utils import timezone


class QueueEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = QueueEntry
        fields = ['id', 'patient_id', 'queue_type', 'priority', 'position_snapshot', 'entered_at', 'active']


class LiveQueuePatientSerializer(serializers.ModelSerializer):
    wait_minutes = serializers.SerializerMethodField()
    latest_assessment = serializers.SerializerMethodField()
    latest_vitals = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            'id', 'name', 'patient_identifier', 'age', 'age_group', 'chief_complaint', 'history_available',
            'current_priority', 'current_queue', 'current_destination',
            'status', 'scenario_tag', 'arrival_time',
            'wait_minutes', 'latest_assessment', 'latest_vitals',
            'assigned_doctor', 'under_scan', 'scan_reports',
            'dynamic_priority_score', 'degradation_rate', 'scheduler_state',
            'last_attended_time'
        ]

    def get_wait_minutes(self, obj):
        if obj.arrival_time:
            delta = timezone.now() - obj.arrival_time
            return int(delta.total_seconds() / 60)
        return 0

    def get_latest_assessment(self, obj):
        a = obj.assessments.order_by('-created_at').first()
        if a:
            return RiskAssessmentSerializer(a).data
        return None

    def get_latest_vitals(self, obj):
        from patients.serializers import VitalReadingSerializer
        v = obj.vital_readings.order_by('-recorded_at').first()
        if v:
            return VitalReadingSerializer(v).data
        return None
