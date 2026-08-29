"""Patient domain models."""
import uuid
from django.db import models


class AgeGroup(models.TextChoices):
    PEDIATRIC = 'pediatric', 'Pediatric'
    ADULT = 'adult', 'Adult'
    GERIATRIC = 'geriatric', 'Geriatric'


class PatientStatus(models.TextChoices):
    WAITING = 'waiting', 'Waiting'
    IN_PROGRESS = 'in_progress', 'In Progress'
    DISCHARGED = 'discharged', 'Discharged'
    ADMITTED = 'admitted', 'Admitted'


class Priority(models.TextChoices):
    P1 = 'P1', 'P1 - Immediate'
    P2 = 'P2', 'P2 - Very Urgent'
    P3 = 'P3', 'P3 - Urgent'
    P4 = 'P4', 'P4 - Less Urgent'
    P5 = 'P5', 'P5 - Non-Urgent'


class Patient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, blank=True)
    patient_identifier = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    arrival_time = models.DateTimeField()
    age = models.PositiveSmallIntegerField()
    age_group = models.CharField(max_length=20, choices=AgeGroup.choices)
    sex = models.CharField(max_length=20, blank=True)
    chief_complaint = models.CharField(max_length=500, blank=True, default='')
    history_available = models.BooleanField(default=True)
    relevant_history = models.TextField(blank=True)
    current_priority = models.CharField(max_length=5, choices=Priority.choices, null=True, blank=True)
    current_queue = models.CharField(max_length=50, blank=True)
    current_destination = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=PatientStatus.choices, default=PatientStatus.WAITING)
    # Simulation metadata
    scenario_tag = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Patient {self.id} ({self.age}y {self.age_group}) - {self.chief_complaint}"

    def get_age_group(self):
        if self.age < 18:
            return AgeGroup.PEDIATRIC
        elif self.age >= 65:
            return AgeGroup.GERIATRIC
        return AgeGroup.ADULT


class VitalReading(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='vital_readings')
    heart_rate = models.FloatField(null=True, blank=True)
    systolic_bp = models.FloatField(null=True, blank=True)
    diastolic_bp = models.FloatField(null=True, blank=True)
    spo2 = models.FloatField(null=True, blank=True)
    respiratory_rate = models.FloatField(null=True, blank=True)
    temperature = models.FloatField(null=True, blank=True)
    mental_status = models.CharField(
        max_length=20,
        choices=[('alert', 'Alert'), ('confused', 'Confused'), ('unresponsive', 'Unresponsive')],
        default='alert'
    )
    recorded_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']

    def __str__(self):
        return f"Vitals for {self.patient_id} at {self.recorded_at}"


class PatientNote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='notes')
    raw_text = models.TextField()
    normalized_symptoms = models.JSONField(default=list)
    extracted_flags = models.JSONField(default=list)
    source = models.CharField(max_length=50, default='intake')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
