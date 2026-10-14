"""Serializers for patients app."""
from rest_framework import serializers
from .models import Patient, VitalReading, PatientNote


class VitalReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = VitalReading
        fields = [
            'id', 'heart_rate', 'systolic_bp', 'diastolic_bp',
            'spo2', 'respiratory_rate', 'temperature', 'mental_status',
            'recorded_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def validate_spo2(self, value):
        if value is not None:
            if value < 50 or value > 100:
                raise serializers.ValidationError("SpO2 must be between 50% and 100%.")
        return value


class PatientNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientNote
        fields = ['id', 'raw_text', 'normalized_symptoms', 'extracted_flags', 'source', 'created_at']
        read_only_fields = ['id', 'normalized_symptoms', 'extracted_flags', 'created_at']


class PatientListSerializer(serializers.ModelSerializer):
    wait_minutes = serializers.SerializerMethodField()
    latest_vitals = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            'id', 'name', 'patient_identifier', 'arrival_time', 'age', 'age_group', 'chief_complaint',
            'history_available', 'current_priority', 'current_queue',
            'current_destination', 'status', 'scenario_tag',
            'wait_minutes', 'latest_vitals', 'created_at', 'updated_at',
            'assigned_doctor', 'under_scan', 'scan_reports',
            'dynamic_priority_score', 'degradation_rate', 'scheduler_state',
            'last_attended_time'
        ]

    def get_wait_minutes(self, obj):
        from django.utils import timezone
        from simulation.models import SimulationState
        sim_state = SimulationState.objects.first()
        current_time = sim_state.sim_time if (sim_state and sim_state.is_running and sim_state.sim_time) else timezone.now()
        if obj.arrival_time:
            delta = current_time - obj.arrival_time
            return int(delta.total_seconds() / 60)
        return 0

    def get_latest_vitals(self, obj):
        v = obj.vital_readings.first()
        if v:
            return VitalReadingSerializer(v).data
        return None


class PatientDetailSerializer(PatientListSerializer):
    vital_readings = VitalReadingSerializer(many=True, read_only=True)
    notes = PatientNoteSerializer(many=True, read_only=True)

    class Meta(PatientListSerializer.Meta):
        fields = PatientListSerializer.Meta.fields + [
            'sex', 'relevant_history', 'vital_readings', 'notes'
        ]


class PatientCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = [
            'name', 'patient_identifier', 'age', 'sex', 'chief_complaint',
            'history_available', 'relevant_history', 'arrival_time', 'scenario_tag',
            'assigned_doctor'
        ]

    def validate_age(self, value):
        if value < 0 or value > 120:
            raise serializers.ValidationError("Age must be between 0 and 120.")
        return value

    def create(self, validated_data):
        age = validated_data.get('age', 30)
        if age < 18:
            age_group = 'pediatric'
        elif age >= 65:
            age_group = 'geriatric'
        else:
            age_group = 'adult'
        validated_data['age_group'] = age_group

        if 'arrival_time' not in validated_data or validated_data['arrival_time'] is None:
            from django.utils import timezone
            validated_data['arrival_time'] = timezone.now()

        return super().create(validated_data)
