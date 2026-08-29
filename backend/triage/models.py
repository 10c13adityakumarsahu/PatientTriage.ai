"""Triage / Risk Assessment models."""
import uuid
from django.db import models
from patients.models import Patient, Priority


class RiskAssessment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='assessments')
    priority = models.CharField(max_length=5, choices=Priority.choices)
    confidence = models.FloatField()  # 0.0 – 1.0
    risk_factors = models.JSONField(default=list)      # list of human-readable strings
    uncertainty_flags = models.JSONField(default=list) # list of flag strings
    missing_fields = models.JSONField(default=list)
    recommended_action = models.CharField(max_length=100, blank=True)
    recommended_destination = models.CharField(max_length=50, blank=True)
    requires_human_review = models.BooleanField(default=False)
    model_version = models.CharField(max_length=50, default='rule-engine-v1')
    ai_decision_support = models.JSONField(null=True, blank=True)
    trigger = models.CharField(max_length=100, blank=True)  # what caused this assessment
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def confidence_label(self):
        if self.confidence >= 0.80:
            return 'high'
        elif self.confidence >= 0.60:
            return 'medium'
        return 'low'

    def __str__(self):
        return f"Assessment {self.id}: {self.priority} ({self.confidence:.0%})"
