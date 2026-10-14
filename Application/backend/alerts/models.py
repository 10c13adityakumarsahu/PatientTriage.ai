"""Alert models."""
import uuid
from django.db import models
from patients.models import Patient


class AlertType(models.TextChoices):
    DETERIORATION = 'deterioration', 'Deterioration'
    WAIT_THRESHOLD = 'wait_threshold', 'Wait Threshold'
    LOW_CONFIDENCE = 'low_confidence', 'Low Confidence'
    CONFLICTING_DATA = 'conflicting_data', 'Conflicting Data'
    CAPACITY_PRESSURE = 'capacity_pressure', 'Capacity Pressure'
    ESCALATION = 'escalation', 'Escalation Required'


class AlertSeverity(models.TextChoices):
    INFO = 'info', 'Info'
    WARNING = 'warning', 'Warning'
    CRITICAL = 'critical', 'Critical'


class Alert(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='alerts', null=True, blank=True)
    alert_type = models.CharField(max_length=30, choices=AlertType.choices)
    severity = models.CharField(max_length=20, choices=AlertSeverity.choices, default=AlertSeverity.WARNING)
    title = models.CharField(max_length=200)
    message = models.TextField()
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_active(self):
        return self.acknowledged_at is None

    def __str__(self):
        return f"Alert [{self.severity}] {self.title}"
