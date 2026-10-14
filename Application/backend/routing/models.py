"""Routing models."""
import uuid
from django.db import models
from patients.models import Patient


class ResourceType(models.TextChoices):
    RESUS_BAY = 'resus_bay', 'Resuscitation Bay'
    TREATMENT_ROOM = 'treatment_room', 'Treatment Room'
    FAST_TRACK_ROOM = 'fast_track_room', 'Fast Track Room'
    OBSERVATION_BED = 'observation_bed', 'Observation Bed'


class Resource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=30, choices=ResourceType.choices)
    capacity = models.PositiveSmallIntegerField(default=1)
    occupied = models.PositiveSmallIntegerField(default=0)
    capabilities = models.JSONField(default=list)
    status = models.CharField(
        max_length=20,
        choices=[('available', 'Available'), ('full', 'Full'), ('offline', 'Offline')],
        default='available'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def available_slots(self):
        return max(0, self.capacity - self.occupied)

    @property
    def utilization_pct(self):
        return round(self.occupied / self.capacity * 100) if self.capacity else 0

    def __str__(self):
        return f"{self.name} ({self.available_slots}/{self.capacity} free)"


class RoutingRecommendation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='routing_recommendations')
    destination = models.CharField(max_length=50)
    rationale = models.TextField()
    confidence = models.FloatField()
    accepted = models.BooleanField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Route for {self.patient_id} → {self.destination}"
