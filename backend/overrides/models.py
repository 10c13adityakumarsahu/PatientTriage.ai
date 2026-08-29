"""Clinician Override models."""
import uuid
from django.db import models
from patients.models import Patient, Priority


class OverrideReason(models.TextChoices):
    CLINICAL_DETERIORATION = 'clinical_deterioration', 'Clinical Deterioration Observed'
    CLINICAL_IMPROVEMENT = 'clinical_improvement', 'Clinical Improvement Observed'
    ADDITIONAL_HISTORY = 'additional_history', 'Additional History Available'
    RESOURCE_CONSTRAINT = 'resource_constraint', 'Resource Constraint'
    PATIENT_PREFERENCE = 'patient_preference', 'Patient Preference'
    OTHER = 'other', 'Other Clinical Judgment'


class ClinicianOverride(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='overrides')
    original_priority = models.CharField(max_length=5, choices=Priority.choices)
    override_priority = models.CharField(max_length=5, choices=Priority.choices)
    original_destination = models.CharField(max_length=50, blank=True)
    override_destination = models.CharField(max_length=50, blank=True)
    reason_code = models.CharField(max_length=50, choices=OverrideReason.choices)
    note = models.TextField(blank=True)
    clinician_id = models.CharField(max_length=100, default='clinician-1')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Override {self.original_priority}→{self.override_priority} by {self.clinician_id}"
