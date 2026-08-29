"""Audit Event models — append-only event log."""
import uuid
from django.db import models


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient_id = models.UUIDField(null=True, blank=True, db_index=True)
    actor_type = models.CharField(
        max_length=20,
        choices=[('ai', 'AI'), ('clinician', 'Clinician'), ('system', 'System'), ('simulation', 'Simulation')]
    )
    actor_id = models.CharField(max_length=100, blank=True)
    event_type = models.CharField(max_length=60, db_index=True)
    old_state = models.JSONField(null=True, blank=True)
    new_state = models.JSONField(null=True, blank=True)
    trigger = models.CharField(max_length=200, blank=True)
    correlation_id = models.UUIDField(null=True, blank=True)
    confidence = models.FloatField(null=True, blank=True)  # if AI-generated
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        # Append-only: no update/delete should be called on these
        managed = True

    def __str__(self):
        return f"AuditEvent [{self.event_type}] patient={self.patient_id} actor={self.actor_type}"

    @classmethod
    def log(cls, event_type, actor_type='system', actor_id='', patient_id=None,
            old_state=None, new_state=None, trigger='', confidence=None, correlation_id=None):
        """Convenience factory for creating audit events."""
        return cls.objects.create(
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            patient_id=patient_id,
            old_state=old_state,
            new_state=new_state,
            trigger=trigger,
            confidence=confidence,
            correlation_id=correlation_id,
        )
