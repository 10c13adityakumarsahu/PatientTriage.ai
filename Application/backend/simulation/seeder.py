"""
Deterministic simulation seeder.
Creates 20 synthetic patients covering all 10 mandatory simulation scenarios.
Seed is deterministic — same seed produces same patients.

All data is synthetic/illustrative — not real patient records.
"""
from datetime import timedelta
from django.utils import timezone

from patients.models import Patient, VitalReading, PatientNote
from routing.models import Resource, ResourceType
from simulation.models import SimulationState
from triage.services import run_triage_assessment
from audit.models import AuditEvent


# 20 curated synthetic patients — scenario-tagged
SYNTHETIC_PATIENTS = [
    # 1. Obvious high-risk — P1 target
    {
        "scenario_tag": "obvious_high_risk",
        "name": "Ramesh Kumar", "patient_identifier": "91-4221-5582-0001",
        "age": 55, "sex": "M",
        "chief_complaint": "severe crushing chest pain radiating to jaw",
        "history_available": True,
        "relevant_history": "Hypertension, smoker",
        "minutes_ago": 5,
        "vitals": {
            "heart_rate": 122, "systolic_bp": 88, "diastolic_bp": 58,
            "spo2": 92, "respiratory_rate": 26, "temperature": 37.1,
            "mental_status": "alert"
        }
    },
    # 2. Stable low-risk — P5 target
    {
        "scenario_tag": "stable_low_risk",
        "name": "Anjali Sharma", "patient_identifier": "91-9081-3321-0002",
        "age": 28, "sex": "F",
        "chief_complaint": "small laceration on finger, minimal bleeding",
        "history_available": True,
        "relevant_history": "None significant",
        "minutes_ago": 45,
        "vitals": {
            "heart_rate": 75, "systolic_bp": 118, "diastolic_bp": 76,
            "spo2": 99, "respiratory_rate": 16, "temperature": 36.8,
            "mental_status": "alert"
        }
    },
    # 3. Ambiguous presentation — medium confidence, AMBER state
    {
        "scenario_tag": "ambiguous",
        "name": "Vikram Patel", "patient_identifier": "91-7742-1209-0003",
        "age": 42, "sex": "M",
        "chief_complaint": "chest tightness and dizziness, came on gradually",
        "history_available": True,
        "relevant_history": "Anxiety disorder, previous panic attacks",
        "minutes_ago": 20,
        "vitals": {
            "heart_rate": 96, "systolic_bp": 128, "diastolic_bp": 82,
            "spo2": 97, "respiratory_rate": 19, "temperature": 36.9,
            "mental_status": "alert"
        }
    },
    # Casualty / John Doe trauma case (no name, unknown history, obvious visual injury)
    {
        "scenario_tag": "trauma_casualty",
        "name": "John Doe (Casualty)", "patient_identifier": "91-0000-0000-0000",
        "age": 35, "sex": "U",
        "chief_complaint": "Trauma casualty: Unconscious, found on roadside after motor vehicle crash. Multiple visible facial lacerations, active bleeding from scalp, right leg visibly deformed.",
        "history_available": False,
        "relevant_history": "",
        "minutes_ago": 12,
        "vitals": {
            "heart_rate": 115, "systolic_bp": 90, "diastolic_bp": 55,
            "spo2": 89, "respiratory_rate": 28, "temperature": 36.6,
            "mental_status": "unresponsive"
        },
        "deterioration_vitals": {
            "heart_rate": 135, "systolic_bp": 72, "diastolic_bp": 45,
            "spo2": 82, "respiratory_rate": 34, "temperature": 36.2,
            "mental_status": "unresponsive"
        }
    },
    # 4. Pediatric patient — age-aware assessment
    {
        "scenario_tag": "pediatric",
        "name": "Baby Priya", "patient_identifier": "91-5012-9988-0004",
        "age": 5, "sex": "F",
        "chief_complaint": "high fever and rapid breathing, refusing feeds",
        "history_available": True,
        "relevant_history": "No prior hospital admissions",
        "minutes_ago": 15,
        "vitals": {
            "heart_rate": 145, "systolic_bp": 90, "diastolic_bp": 55,
            "spo2": 94, "respiratory_rate": 48, "temperature": 39.8,
            "mental_status": "alert"
        }
    },
    # 5. Geriatric patient — age-aware, no history
    {
        "scenario_tag": "geriatric",
        "name": "Harbhajan Singh", "patient_identifier": "91-3320-7761-0005",
        "age": 78, "sex": "M",
        "chief_complaint": "shortness of breath, started this morning",
        "history_available": False,
        "relevant_history": "",
        "minutes_ago": 25,
        "vitals": {
            "heart_rate": 108, "systolic_bp": 148, "diastolic_bp": 92,
            "spo2": 91, "respiratory_rate": 24, "temperature": 37.6,
            "mental_status": "confused"
        }
    },
    # 6. Zero-history patient — confidence must decrease, not risk
    {
        "scenario_tag": "zero_history",
        "name": "Rajesh Mehta", "patient_identifier": "91-1122-3344-0006",
        "age": 35, "sex": "U",
        "chief_complaint": "generalized weakness and confusion",
        "history_available": False,
        "relevant_history": "",
        "minutes_ago": 10,
        "vitals": {
            "heart_rate": 104, "systolic_bp": 102, "diastolic_bp": 66,
            "spo2": 95, "respiratory_rate": 22, "temperature": 38.4,
            "mental_status": "confused"
        }
    },
    # 7. Deteriorating patient — starts P3, worsens to P1
    {
        "scenario_tag": "deteriorating",
        "name": "Kavita Rao", "patient_identifier": "91-8877-6655-0007",
        "age": 61, "sex": "F",
        "chief_complaint": "shortness of breath and increasing chest tightness",
        "history_available": True,
        "relevant_history": "COPD, ex-smoker",
        "minutes_ago": 35,
        "vitals": {
            "heart_rate": 101, "systolic_bp": 115, "diastolic_bp": 74,
            "spo2": 93, "respiratory_rate": 23, "temperature": 37.2,
            "mental_status": "alert"
        },
        "deterioration_vitals": {
            "heart_rate": 138, "systolic_bp": 84, "diastolic_bp": 52,
            "spo2": 86, "respiratory_rate": 34, "temperature": 37.8,
            "mental_status": "confused"
        }
    },
    # 8. Long-wait patient — stable but approaching threshold
    {
        "scenario_tag": "long_wait",
        "name": "Aditya Verma", "patient_identifier": "91-4455-6677-0008",
        "age": 50, "sex": "M",
        "chief_complaint": "moderate abdominal pain",
        "history_available": True,
        "relevant_history": "IBS, no prior surgery",
        "minutes_ago": 75,
        "vitals": {
            "heart_rate": 88, "systolic_bp": 124, "diastolic_bp": 80,
            "spo2": 98, "respiratory_rate": 17, "temperature": 37.0,
            "mental_status": "alert"
        }
    },
    # 9. Conflicting signals — high HR but normal BP, no chest pain
    {
        "scenario_tag": "conflicting_signals",
        "name": "Meera Nair", "patient_identifier": "91-2233-4455-0009",
        "age": 38, "sex": "F",
        "chief_complaint": "palpitations, no chest pain, no dizziness",
        "history_available": True,
        "relevant_history": "Hyperthyroidism on medication",
        "minutes_ago": 30,
        "vitals": {
            "heart_rate": 148, "systolic_bp": 122, "diastolic_bp": 78,
            "spo2": 98, "respiratory_rate": 16, "temperature": 37.3,
            "mental_status": "alert"
        }
    },
    # 10. Override candidate — clinician will change recommendation
    {
        "scenario_tag": "override_candidate",
        "name": "Sunil Dutt", "patient_identifier": "91-9900-1122-0010",
        "age": 45, "sex": "M",
        "chief_complaint": "mild headache for 2 days",
        "history_available": True,
        "relevant_history": "Migraines, on triptans",
        "minutes_ago": 55,
        "vitals": {
            "heart_rate": 80, "systolic_bp": 126, "diastolic_bp": 82,
            "spo2": 99, "respiratory_rate": 15, "temperature": 36.7,
            "mental_status": "alert"
        }
    },
    # 11–20: Additional patients for realistic queue density
    {
        "scenario_tag": "routine_adult",
        "name": "Pooja Hegde", "patient_identifier": "91-7766-5544-0011",
        "age": 33, "sex": "F",
        "chief_complaint": "vomiting and nausea for 12 hours",
        "history_available": True, "relevant_history": "None",
        "minutes_ago": 40,
        "vitals": {
            "heart_rate": 92, "systolic_bp": 112, "diastolic_bp": 70,
            "spo2": 98, "respiratory_rate": 18, "temperature": 37.4,
            "mental_status": "alert"
        }
    },
    {
        "scenario_tag": "pediatric_minor",
        "name": "Rahul Deshmukh", "patient_identifier": "91-3344-5566-0012",
        "age": 8, "sex": "M",
        "chief_complaint": "fall from bicycle, arm pain",
        "history_available": True, "relevant_history": "Healthy child",
        "minutes_ago": 22,
        "vitals": {
            "heart_rate": 105, "systolic_bp": 95, "diastolic_bp": 62,
            "spo2": 99, "respiratory_rate": 22, "temperature": 36.9,
            "mental_status": "alert"
        }
    },
    {
        "scenario_tag": "geriatric_fall",
        "name": "Savitri Devi", "patient_identifier": "91-5566-7788-0013",
        "age": 82, "sex": "F",
        "chief_complaint": "fall at home, hip pain",
        "history_available": True,
        "relevant_history": "Osteoporosis, warfarin",
        "minutes_ago": 18,
        "vitals": {
            "heart_rate": 88, "systolic_bp": 138, "diastolic_bp": 84,
            "spo2": 97, "respiratory_rate": 18, "temperature": 36.5,
            "mental_status": "alert"
        }
    },
    {
        "scenario_tag": "sepsis_concern",
        "name": "Mohammad Ali", "patient_identifier": "91-9988-7766-0014",
        "age": 67, "sex": "M",
        "chief_complaint": "fever, confusion, and lethargy",
        "history_available": True,
        "relevant_history": "Diabetes, recent UTI",
        "minutes_ago": 8,
        "vitals": {
            "heart_rate": 118, "systolic_bp": 94, "diastolic_bp": 62,
            "spo2": 94, "respiratory_rate": 28, "temperature": 39.2,
            "mental_status": "confused"
        }
    },
    {
        "scenario_tag": "allergic_reaction",
        "name": "Aisha Khan", "patient_identifier": "91-4433-2211-0015",
        "age": 24, "sex": "F",
        "chief_complaint": "allergic reaction after eating shellfish, facial swelling",
        "history_available": False, "relevant_history": "",
        "minutes_ago": 3,
        "vitals": {
            "heart_rate": 116, "systolic_bp": 100, "diastolic_bp": 68,
            "spo2": 96, "respiratory_rate": 22, "temperature": 37.0,
            "mental_status": "alert"
        }
    },
    {
        "scenario_tag": "chest_pain_low_risk",
        "name": "Vijay Mallya", "patient_identifier": "91-1111-2222-0016",
        "age": 29, "sex": "M",
        "chief_complaint": "sharp chest pain on deep breath",
        "history_available": True,
        "relevant_history": "Recent respiratory illness",
        "minutes_ago": 50,
        "vitals": {
            "heart_rate": 84, "systolic_bp": 122, "diastolic_bp": 78,
            "spo2": 98, "respiratory_rate": 17, "temperature": 37.1,
            "mental_status": "alert"
        }
    },
    {
        "scenario_tag": "minor_trauma",
        "name": "Gaurav Gupta", "patient_identifier": "91-8888-9999-0017",
        "age": 19, "sex": "M",
        "chief_complaint": "ankle sprain from sport",
        "history_available": True, "relevant_history": "Healthy",
        "minutes_ago": 60,
        "vitals": {
            "heart_rate": 78, "systolic_bp": 118, "diastolic_bp": 72,
            "spo2": 100, "respiratory_rate": 16, "temperature": 36.6,
            "mental_status": "alert"
        }
    },
    {
        "scenario_tag": "stroke_concern",
        "name": "Leela Prasad", "patient_identifier": "91-6666-7777-0018",
        "age": 71, "sex": "F",
        "chief_complaint": "sudden weakness in right arm and slurred speech",
        "history_available": True,
        "relevant_history": "Hypertension, atrial fibrillation",
        "minutes_ago": 12,
        "vitals": {
            "heart_rate": 94, "systolic_bp": 178, "diastolic_bp": 102,
            "spo2": 96, "respiratory_rate": 20, "temperature": 36.9,
            "mental_status": "confused"
        }
    },
    {
        "scenario_tag": "routine_elderly",
        "name": "Pranab Mukherjee", "patient_identifier": "91-5555-4444-0019",
        "age": 69, "sex": "M",
        "chief_complaint": "medication review and blood pressure check",
        "history_available": True,
        "relevant_history": "Hypertension, diabetes",
        "minutes_ago": 90,
        "vitals": {
            "heart_rate": 72, "systolic_bp": 142, "diastolic_bp": 86,
            "spo2": 97, "respiratory_rate": 16, "temperature": 36.8,
            "mental_status": "alert"
        }
    },
    {
        "scenario_tag": "moderate_pain",
        "name": "Shalini Sen", "patient_identifier": "91-3333-2222-0020",
        "age": 44, "sex": "F",
        "chief_complaint": "severe back pain, unable to stand",
        "history_available": True,
        "relevant_history": "Previous disc herniation",
        "minutes_ago": 28,
        "vitals": {
            "heart_rate": 95, "systolic_bp": 130, "diastolic_bp": 84,
            "spo2": 98, "respiratory_rate": 19, "temperature": 36.9,
            "mental_status": "alert"
        }
    },
]

RESOURCES_SEED = [
    {"name": "Resus Bay 1", "resource_type": "resus_bay", "capacity": 2, "occupied": 0},
    {"name": "Resus Bay 2", "resource_type": "resus_bay", "capacity": 2, "occupied": 1},
    {"name": "Treatment Room A", "resource_type": "treatment_room", "capacity": 4, "occupied": 2},
    {"name": "Treatment Room B", "resource_type": "treatment_room", "capacity": 4, "occupied": 1},
    {"name": "Fast Track 1", "resource_type": "fast_track_room", "capacity": 6, "occupied": 2},
    {"name": "Observation Bay", "resource_type": "observation_bed", "capacity": 8, "occupied": 3},
]


def seed_baseline():
    """
    Create baseline scenario with 15 initial synthetic patients.
    Deterministic — same patients every time seed is called on a clean DB.
    """
    now = timezone.now()

    # Clear existing sim data
    _clear_simulation_data()

    # Seed resources
    for r in RESOURCES_SEED:
        Resource.objects.create(**r)

    # Create SimulationState
    sim_state = SimulationState.objects.create(
        scenario_name='baseline',
        surge_active=False,
        sim_time=now,
        seed=42,
        is_running=True,
    )

    created_patients = []
    for patient_orig in SYNTHETIC_PATIENTS[:15]:
        patient_data = patient_orig.copy()
        arrival_time = now - timedelta(minutes=patient_data.pop('minutes_ago', 0))
        
        # Pop vitals and deterioration vitals so they are not saved during seed
        vitals_data = patient_data.pop('vitals', None)
        deterioration_vitals = patient_data.pop('deterioration_vitals', None)

        patient = Patient.objects.create(
            arrival_time=arrival_time,
            status='waiting',
            scheduler_state='blocked',
            **patient_data,
        )

        # Set age group
        if patient.age < 18:
            patient.age_group = 'pediatric'
        elif patient.age >= 65:
            patient.age_group = 'geriatric'
        else:
            patient.age_group = 'adult'
        patient.save(update_fields=['age_group'])

        # Store deterioration vitals on patient for later use
        if deterioration_vitals:
            patient._deterioration_vitals = deterioration_vitals

        created_patients.append(patient)

        AuditEvent.log(
            event_type='simulation_patient_created',
            actor_type='simulation',
            patient_id=patient.id,
            new_state={
                'scenario_tag': patient.scenario_tag,
                'age': patient.age,
                'age_group': patient.age_group,
            },
            trigger='seed_baseline',
        )

    # Create default active QueueEntry for each patient to place them in general waiting queue
    from queues.models import QueueEntry
    for p in created_patients:
        QueueEntry.objects.create(
            patient=p,
            queue_type='general_emergency',
            priority='P4',
            active=True
        )

    return created_patients


def intake_next_patient():
    """
    Seed the next patient from the SYNTHETIC_PATIENTS list that isn't already in the database.
    Allows testing/walkthroughs to simulate individual patient intake events sequentially.
    """
    now = timezone.now()
    existing_tags = set(Patient.objects.filter(scenario_tag__isnull=False).values_list('scenario_tag', flat=True))

    next_patient_data = None
    for p in SYNTHETIC_PATIENTS:
        if p['scenario_tag'] not in existing_tags:
            next_patient_data = p
            break

    if not next_patient_data:
        return None  # All 20 synthetic patients have been seeded!

    # Seed this single patient
    patient_data = next_patient_data.copy()
    arrival_time = now - timedelta(minutes=patient_data.pop('minutes_ago', 0))
    vitals_data = patient_data.pop('vitals', None)
    deterioration_vitals = patient_data.pop('deterioration_vitals', None)

    patient = Patient.objects.create(
        arrival_time=arrival_time,
        status='waiting',
        **patient_data,
    )

    if patient.age < 18:
        patient.age_group = 'pediatric'
    elif patient.age >= 65:
        patient.age_group = 'geriatric'
    else:
        patient.age_group = 'adult'
    patient.save(update_fields=['age_group'])

    if vitals_data:
        VitalReading.objects.create(
            patient=patient,
            recorded_at=arrival_time + timedelta(minutes=3),
            **vitals_data
        )

    from decision_engine.normalizer import normalize_symptoms
    tokens, flags = normalize_symptoms(patient.chief_complaint)
    PatientNote.objects.create(
        patient=patient,
        raw_text=patient.chief_complaint,
        normalized_symptoms=tokens,
        extracted_flags=flags,
        source='intake',
    )

    # Run initial triage assessment
    run_triage_assessment(patient, trigger='initial_assessment')

    if deterioration_vitals:
        patient._deterioration_vitals = deterioration_vitals

    AuditEvent.log(
        event_type='simulation_patient_created',
        actor_type='simulation',
        patient_id=patient.id,
        new_state={
            'scenario_tag': patient.scenario_tag,
            'age': patient.age,
            'age_group': patient.age_group,
        },
        trigger='intake_next_patient',
    )
    return patient


def trigger_deterioration(patient_id):
    """Apply deterioration vitals to a patient and reassess."""
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return None

    # Get preset deterioration vitals from scenario data
    scenario_tag = patient.scenario_tag
    deterioration_vitals = None
    for p in SYNTHETIC_PATIENTS:
        if p.get('scenario_tag') == scenario_tag and 'deterioration_vitals' in p:
            deterioration_vitals = p['deterioration_vitals']
            break

    if not deterioration_vitals:
        # Generic deterioration: worsen key vitals
        latest = patient.vital_readings.order_by('-recorded_at').first()
        if latest:
            deterioration_vitals = {
                'heart_rate': min(160, (latest.heart_rate or 80) + 30),
                'systolic_bp': max(80, (latest.systolic_bp or 120) - 25),
                'diastolic_bp': max(50, (latest.diastolic_bp or 80) - 15),
                'spo2': max(82, (latest.spo2 or 97) - 8),
                'respiratory_rate': min(40, (latest.respiratory_rate or 18) + 12),
                'temperature': min(40.0, (latest.temperature or 37.0) + 0.8),
                'mental_status': 'confused',
            }
        else:
            deterioration_vitals = {
                'heart_rate': 125,
                'systolic_bp': 85,
                'diastolic_bp': 55,
                'spo2': 88,
                'respiratory_rate': 28,
                'temperature': 38.5,
                'mental_status': 'confused',
            }

    VitalReading.objects.create(
        patient=patient,
        recorded_at=timezone.now(),
        **deterioration_vitals
    )

    AuditEvent.log(
        event_type='deterioration_triggered',
        actor_type='simulation',
        patient_id=patient.id,
        new_state=deterioration_vitals,
        trigger='simulation_deterioration',
    )

    from simulation.broadcast import broadcast_event
    broadcast_event('patient.updated', {'patient_id': str(patient.id), 'type': 'deterioration'})

    return run_triage_assessment(patient, trigger='deterioration_detected')


def trigger_surge():
    """
    Activate 3× surge mode and add extra patients.
    """
    sim = SimulationState.objects.first()
    if sim:
        if sim.surge_active:
            return []
        sim.surge_active = True
        sim.save()

    now = timezone.now()
    surge_patients = []

    # Add 10 additional surge patients (on top of baseline 20)
    surge_data = [
        {"name": "Suresh Raina", "patient_identifier": "91-2211-8899-0021",
         "age": 52, "sex": "M", "chief_complaint": "chest pain", "history_available": False,
         "relevant_history": "", "vitals": {"heart_rate": 110, "systolic_bp": 96, "diastolic_bp": 60,
                                             "spo2": 93, "respiratory_rate": 24, "temperature": 37.2,
                                             "mental_status": "alert"}},
        {"name": "Baby Dia", "patient_identifier": "91-6655-4433-0022",
         "age": 7, "sex": "F", "chief_complaint": "difficulty breathing and rash", "history_available": True,
         "relevant_history": "Asthma", "vitals": {"heart_rate": 140, "systolic_bp": 88, "diastolic_bp": 55,
                                                   "spo2": 92, "respiratory_rate": 44, "temperature": 38.9,
                                                   "mental_status": "alert"}},
        {"name": "Madan Lal", "patient_identifier": "91-8877-1122-0023",
         "age": 75, "sex": "M", "chief_complaint": "fall and confusion", "history_available": False,
         "relevant_history": "", "vitals": {"heart_rate": 92, "systolic_bp": 140, "diastolic_bp": 86,
                                             "spo2": 95, "respiratory_rate": 20, "temperature": 37.1,
                                             "mental_status": "confused"}},
        {"name": "Deepika Padukone", "patient_identifier": "91-9900-5566-0024",
         "age": 31, "sex": "F", "chief_complaint": "severe abdominal pain", "history_available": True,
         "relevant_history": "None", "vitals": {"heart_rate": 105, "systolic_bp": 108, "diastolic_bp": 70,
                                                 "spo2": 97, "respiratory_rate": 21, "temperature": 37.8,
                                                 "mental_status": "alert"}},
        {"name": "Kapil Dev", "patient_identifier": "91-5544-2233-0025",
         "age": 48, "sex": "M", "chief_complaint": "palpitations and shortness of breath", "history_available": True,
         "relevant_history": "AF", "vitals": {"heart_rate": 152, "systolic_bp": 118, "diastolic_bp": 76,
                                               "spo2": 94, "respiratory_rate": 22, "temperature": 36.9,
                                               "mental_status": "alert"}},
    ]

    for data in surge_data:
        vitals = data.pop('vitals')
        p = Patient.objects.create(
            arrival_time=now - timedelta(minutes=2),
            status='waiting',
            scenario_tag='surge',
            age_group='pediatric' if data['age'] < 18 else ('geriatric' if data['age'] >= 65 else 'adult'),
            **data
        )
        VitalReading.objects.create(patient=p, recorded_at=now, **vitals)
        from decision_engine.normalizer import normalize_symptoms
        tokens, flags = normalize_symptoms(p.chief_complaint)
        PatientNote.objects.create(patient=p, raw_text=p.chief_complaint,
                                   normalized_symptoms=tokens, extracted_flags=flags)
        run_triage_assessment(p, trigger='surge_arrival')
        surge_patients.append(p)

    AuditEvent.log(
        event_type='surge_activated',
        actor_type='simulation',
        new_state={'surge_active': True, 'extra_patients': len(surge_patients)},
        trigger='surge_trigger',
    )

    from routing.scheduler import recalculate_resource_occupancy
    recalculate_resource_occupancy()

    from simulation.broadcast import broadcast_event
    broadcast_event('surge.started', {'active': True, 'extra_patients': len(surge_patients)})

    return surge_patients


def reset_simulation():
    """Reset all simulation data to clean state."""
    _clear_simulation_data()
    AuditEvent.log(
        event_type='simulation_reset',
        actor_type='simulation',
        trigger='reset_command',
    )
    from simulation.broadcast import broadcast_event
    broadcast_event('simulation.reset', {'reset': True})


def _clear_simulation_data():
    """Delete all simulation-generated data."""
    from patients.models import Patient, VitalReading, PatientNote
    from triage.models import RiskAssessment
    from queues.models import QueueEntry
    from routing.models import Resource, RoutingRecommendation
    from alerts.models import Alert
    from overrides.models import ClinicianOverride
    from audit.models import AuditEvent

    Patient.objects.all().delete()
    Resource.objects.all().delete()
    SimulationState.objects.all().delete()
    # AuditEvents are append-only — keep them across resets for demo auditability
    # but add a reset marker event


def simulate_gradual_flow(current_time):
    """
    Find patients in 'waiting' status who have no vitals,
    and gradually populate vitals for some of them, normalize symptoms, and run triage.
    This simulates gradual intake completion and triage assessment flow during demo runs.
    """
    from patients.models import Patient, VitalReading, PatientNote
    from triage.services import run_triage_assessment
    from django.db.models import Count
    
    # Annotate patients with vital reading count
    pending_patients = Patient.objects.annotate(vitals_count=Count('vital_readings')).filter(status='waiting', vitals_count=0)
    
    if not pending_patients.exists():
        return 0
        
    # Process exactly 1 patient per tick for a true one-by-one sequential flow
    patients_to_process = list(pending_patients[:1])
    processed_count = 0
    
    for patient in patients_to_process:
        # Find curated vitals from the static SYNTHETIC_PATIENTS list matching this patient
        matched_data = None
        for p_orig in SYNTHETIC_PATIENTS:
            if p_orig['patient_identifier'] == patient.patient_identifier:
                matched_data = p_orig
                break
                
        if matched_data and 'vitals' in matched_data:
            vitals = matched_data['vitals']
            # Create vital reading
            VitalReading.objects.create(
                patient=patient,
                recorded_at=current_time,
                **vitals
            )
            # Create symptoms note/observations
            from decision_engine.normalizer import normalize_symptoms
            tokens, flags = normalize_symptoms(patient.chief_complaint)
            PatientNote.objects.create(
                patient=patient,
                raw_text=patient.chief_complaint,
                normalized_symptoms=tokens,
                extracted_flags=flags,
                source='intake'
            )
            # Run triage assessment
            run_triage_assessment(patient, trigger='gradual_simulation_tick')
            processed_count += 1
            
    return processed_count


def get_next_patient_intake_data():
    """
    Find the next patient from SYNTHETIC_PATIENTS that hasn't been registered in the database yet,
    and return their intake-related demographics (demographics & chief complaint).
    """
    from patients.models import Patient
    existing_tags = set(Patient.objects.filter(scenario_tag__isnull=False).values_list('scenario_tag', flat=True))
    for p in SYNTHETIC_PATIENTS:
        if p['scenario_tag'] not in existing_tags:
            return {
                'name': p['name'],
                'patient_identifier': p['patient_identifier'],
                'age': p['age'],
                'sex': p['sex'],
                'chief_complaint': p['chief_complaint'],
                'history_available': p['history_available'],
                'relevant_history': p['relevant_history'],
            }
    return None
