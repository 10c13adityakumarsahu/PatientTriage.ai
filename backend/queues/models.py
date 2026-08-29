"""Queue models."""
import uuid
from django.db import models
from patients.models import Patient, Priority


class QueueType(models.TextChoices):
    RESUSCITATION = 'resuscitation', 'Resuscitation'
    GENERAL_EMERGENCY = 'general_emergency', 'General Emergency'
    FAST_TRACK = 'fast_track', 'Fast Track'
    OBSERVATION = 'observation', 'Observation'


class QueueEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='queue_entries')
    queue_type = models.CharField(max_length=30, choices=QueueType.choices)
    priority = models.CharField(max_length=5, choices=Priority.choices)
    position_snapshot = models.PositiveSmallIntegerField(null=True, blank=True)
    entered_at = models.DateTimeField(auto_now_add=True)
    exited_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['priority', 'entered_at']

    def __str__(self):
        return f"QueueEntry {self.patient_id} in {self.queue_type} ({self.priority})"
