"""Triage serializers."""
from rest_framework import serializers
from .models import RiskAssessment


class RiskAssessmentSerializer(serializers.ModelSerializer):
    confidence_label = serializers.SerializerMethodField()

    class Meta:
        model = RiskAssessment
        fields = [
            'id', 'patient_id', 'priority', 'confidence', 'confidence_label',
            'risk_factors', 'uncertainty_flags', 'missing_fields',
            'recommended_action', 'recommended_destination',
            'requires_human_review', 'model_version', 'ai_decision_support',
            'confidence_breakdown', 'ai_mode', 'trigger', 'created_at'
        ]

    def get_confidence_label(self, obj):
        return obj.confidence_label()
