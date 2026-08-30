"""
OS-like CPU Scheduler for clinical resources.
Doctors on duty represent CPU cores.
Scans and vitals represent I/O operations.
Triage priority and time decay represent dynamic priority scheduling.
"""
from django.utils import timezone
from django.db import transaction
from patients.models import Patient, PatientStatus
from queues.models import QueueEntry
from audit.models import AuditEvent
from decision_engine.ai_assistant import reevaluate_reports_ai
from simulation.models import SimulationState

# Clinician Directory representing CPU Cores
DOCTORS = [
    {"name": "Dr. Kapoor", "department": "cardiac_care"},
    {"name": "Dr. Sharma", "department": "pediatrics"},
    {"name": "Dr. Roy", "department": "orthopedics"},
    {"name": "Dr. Patel", "department": "resuscitation"},
    {"name": "Dr. Sen", "department": "cardiac_care"},
    {"name": "Dr. Joshi", "department": "general_medicine"},
    {"name": "Dr. Gupta", "department": "general_medicine"},
    {"name": "Dr. Iyer", "department": "general_medicine"},
]

def generate_simulated_report(chief_complaint, scenario_tag):
    cc = (chief_complaint or "").lower()
    tag = scenario_tag or ""
    
    if tag == "obvious_high_risk" or "crushing chest" in cc:
        return "ECG shows ST-segment elevation in leads V2-V5, suggesting acute anterior myocardial infarction (STEMI). Cardiac enzyme markers (Troponin T) elevated."
    elif tag == "stroke_concern" or "slurred speech" in cc or "stroke" in cc:
        return "Non-contrast Head CT demonstrates a focal area of acute ischemic infarction in the left MCA territory. No acute intracranial hemorrhage or mass effect observed."
    elif tag == "ambiguous" or "chest tightness" in cc:
        return "CTA Chest reveals no evidence of pulmonary embolism, aortic dissection, or acute coronary occlusion. Lungs are clear, cardiac silhouette is normal."
    elif tag == "pediatric" or "baby" in cc or "fever" in cc:
        return "Urinalysis shows marked pyuria (WBC > 50/hpf) and positive nitrites, consistent with acute urinary tract infection (UTI). Blood culture pending."
    elif tag == "geriatric" or "shortness of breath" in cc:
        return "Chest X-ray shows bibasilar patchy infiltrates and a small right-sided pleural effusion, consistent with acute bacterial pneumonia."
    elif tag == "minor_trauma" or "ankle" in cc or "fracture" in cc:
        return "Plain radiographs of the ankle reveal a non-displaced fracture of the lateral malleolus. Joint spacing is preserved, no secondary dislocation."
    elif "abdominal" in cc or "stomach" in cc:
        return "CT Abdomen/Pelvis reveals a fluid-filled, dilated appendix with periappendiceal fat stranding, consistent with acute appendicitis."
    else:
        return "Diagnostic scan findings are within normal physiological limits. No acute focal abnormalities, active hemorrhage, or critical pathologies detected."

def recalculate_resource_occupancy():
    """
    Recalculates ED resource utilization dynamically from current database patient statuses.
    """
    from routing.models import Resource
    
    # 1. Reset occupied count to 0 for all resources
    resources = Resource.objects.all()
    resource_map = {r.resource_type: r for r in resources}
    for r in resources:
        r.occupied = 0
        
    # 2. Iterate over active patients in ED
    active_patients = Patient.objects.filter(status__in=['in_progress', 'admitted'])
    
    for p in active_patients:
        if p.status == 'admitted':
            # Admitted patients occupy observation beds
            if 'observation_bed' in resource_map:
                resource_map['observation_bed'].occupied += 1
        elif p.status == 'in_progress':
            # In progress patients occupy resuscitation bays or treatment rooms
            dest = p.current_destination or "general_medicine"
            if dest == 'resuscitation':
                if 'resus_bay' in resource_map:
                    resource_map['resus_bay'].occupied += 1
            elif dest in ['cardiac_care', 'pediatrics', 'orthopedics', 'general_medicine']:
                if dest == 'pediatrics':
                    if 'fast_track_room' in resource_map:
                        resource_map['fast_track_room'].occupied += 1
                    elif 'treatment_room' in resource_map:
                        resource_map['treatment_room'].occupied += 1
                else:
                    if 'treatment_room' in resource_map:
                        resource_map['treatment_room'].occupied += 1
                        
    # 3. Save resources with capped values
    for r in resources:
        r.occupied = min(r.capacity, r.occupied)
        if r.occupied >= r.capacity:
            r.status = 'full'
        else:
            r.status = 'available'
        r.save()


@transaction.atomic
def run_scheduler_cycle(stage=None):
    """
    Executes one scheduling cycle:
    stage='io_completion': Complete active scans (advance I/O) and trigger AI re-evaluation.
    stage='priority_aging': Calculate dynamic priority scores with waiting decay and I/O boosts (aging).
    stage='core_allocation': Map free doctors (CPU cores) to waiting patients (ready processes).
    If stage is None: executes all stages.
    """
    sim_state = SimulationState.objects.first()
    current_time = sim_state.sim_time if (sim_state and sim_state.is_running and sim_state.sim_time) else timezone.now()
    
    # ── 1. ADVANCE I/O: SCAN COMPLETION ──
    if stage is None or stage == 'io_completion':
        scanned_patients = Patient.objects.filter(status='waiting', under_scan=True)
        completed_scans = []
        
        for patient in scanned_patients:
            # Complete scan
            patient.under_scan = False
            patient.scheduler_state = 'ready'
            patient.last_attended_time = current_time
            
            # Generate report
            report = generate_simulated_report(patient.chief_complaint, patient.scenario_tag)
            patient.scan_reports = report
            
            # Re-evaluate with AI
            ai_res = reevaluate_reports_ai(patient.chief_complaint, "Diagnostic Scan", report)
            
            old_priority = patient.current_priority
            new_priority = ai_res.get("priority", "P4")
            
            # Update priority, destination, and confidence based on scan
            patient.current_priority = new_priority
            patient.current_destination = "general_emergency" if ai_res.get("confidence", 1.0) < 0.60 else (patient.current_destination or "general_emergency")
            patient.current_queue = patient.current_destination
            
            # Save audit event
            AuditEvent.log(
                event_type='scan_completed',
                actor_type='system',
                patient_id=patient.id,
                old_state={'priority': old_priority, 'under_scan': True},
                new_state={
                    'priority': new_priority, 
                    'under_scan': False, 
                    'scan_reports': report[:100] + "...",
                    'findings_status': ai_res.get("findings_status")
                },
                trigger='scan_completion_reevaluation',
                confidence=ai_res.get("confidence", 0.90)
            )
            
            # Give unblocked patient an I/O priority boost (+0.25)
            patient._io_boost = True
            completed_scans.append(patient)
            patient.save()

    # ── 2. CALCULATE DYNAMIC SCHEDULING PRIORITY (AGING) ──
    if stage is None or stage == 'priority_aging':
        waiting_patients = Patient.objects.filter(status='waiting')
        prio_base = {"P1": 0.90, "P2": 0.70, "P3": 0.50, "P4": 0.30, "P5": 0.10}
        
        for p in waiting_patients:
            has_vitals = p.vital_readings.exists()
            
            if not has_vitals:
                p.scheduler_state = 'blocked'
                p.dynamic_priority_score = 0.0
            elif p.under_scan:
                p.scheduler_state = 'blocked'
                p.dynamic_priority_score = 0.0
            else:
                p.scheduler_state = 'ready'
                
                # Aging formula: Base Triage Score + wait time * degradation rate
                base_score = prio_base.get(p.current_priority, 0.10)
                wait_min = 0
                if p.arrival_time:
                    wait_min = int((current_time - p.arrival_time).total_seconds() / 60)
                
                decay_increment = wait_min * p.degradation_rate
                
                # I/O Boost if scan completed in this cycle
                io_boost = 0.25 if getattr(p, '_io_boost', False) or (p.scan_reports and not p.assigned_doctor) else 0.0
                
                p.dynamic_priority_score = min(2.0, base_score + decay_increment + io_boost)
                
            p.save(update_fields=['scheduler_state', 'dynamic_priority_score'])

    # ── 3. CORE ALLOCATION: DOCTOR ASSIGNMENT ──
    if stage is None or stage == 'core_allocation':
        # Occupied doctors running on CPU (status = 'in_progress')
        in_progress_patients = Patient.objects.filter(status='in_progress')
        occupied_docs = set(in_progress_patients.exclude(assigned_doctor__isnull=True).values_list('assigned_doctor', flat=True))
        
        # Ready patients (status = 'waiting', state = 'ready') sorted by score descending
        ready_patients = list(Patient.objects.filter(status='waiting', scheduler_state='ready').order_by('-dynamic_priority_score'))
        
        for p in ready_patients:
            # If doctor is already assigned (from past history or manual assignment)
            if p.assigned_doctor:
                if p.assigned_doctor not in occupied_docs:
                    # Core is free, schedule!
                    p.status = 'in_progress'
                    p.scheduler_state = 'running'
                    p.last_attended_time = current_time
                    p.save(update_fields=['status', 'scheduler_state', 'last_attended_time'])
                    occupied_docs.add(p.assigned_doctor)
                    
                    # Log audit
                    AuditEvent.log(
                        event_type='patient_scheduled',
                        actor_type='system',
                        patient_id=p.id,
                        new_state={'status': 'in_progress', 'assigned_doctor': p.assigned_doctor},
                        trigger='scheduler_assigned_history_doc'
                    )
                    continue
                else:
                    # Core is busy, process remains blocked/waiting
                    continue
            
            # Match patient department to an available doctor core
            target_dept = p.current_destination or "general_medicine"
            available_doctor = None
            
            # Try to find a doctor in their recommended department
            for doc in DOCTORS:
                if doc['department'] == target_dept and doc['name'] not in occupied_docs:
                    available_doctor = doc['name']
                    break
                    
            # If no doctor in department, try General Medicine fallback
            if not available_doctor:
                for doc in DOCTORS:
                    if doc['department'] == 'general_medicine' and doc['name'] not in occupied_docs:
                        available_doctor = doc['name']
                        break
                        
            # If we found an available doctor core, allocate!
            if available_doctor:
                p.assigned_doctor = available_doctor
                p.status = 'in_progress'
                p.scheduler_state = 'running'
                p.last_attended_time = current_time
                p.save(update_fields=['assigned_doctor', 'status', 'scheduler_state', 'last_attended_time'])
                occupied_docs.add(available_doctor)
                
                # Log audit
                AuditEvent.log(
                    event_type='patient_scheduled',
                    actor_type='system',
                    patient_id=p.id,
                    new_state={'status': 'in_progress', 'assigned_doctor': available_doctor},
                    trigger='scheduler_assigned_auto_doc'
                )
                
                # Update QueueEntry
                QueueEntry.objects.filter(patient=p, active=True).update(active=False, exited_at=timezone.now())
                QueueEntry.objects.create(
                    patient=p,
                    queue_type=p.current_queue or "general_emergency",
                    priority=p.current_priority or "P4",
                    active=True
                )

    # ── 4. RECOMPUTE RESOURCE OCCUPANCY ──
    recalculate_resource_occupancy()
