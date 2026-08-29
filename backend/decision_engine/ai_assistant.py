"""
AI Clinical Assistant — simulates deterministic, seedable clinical intelligence.
Analyzes chief complaints and history to determine complexity, monitoring criteria,
suggested tests, and emergency medications in compliance with safety constraints.
"""

def analyze_symptoms_ai(chief_complaint, relevant_history="", age=None, sex=""):
    """
    Parses symptoms to return simulated expert decision support.
    """
    # Convert inputs to lowercase
    cc = chief_complaint.lower() if chief_complaint else ""
    hist = relevant_history.lower() if relevant_history else ""
    combined = f"{cc} {hist}".strip()
    
    if not combined:
        return None

    # Default fallback - strict: suggest nothing without data or surety
    complexity = "Low"
    rationale = "Vague or non-specific presentation. Standard clinical monitoring required."
    criteria = [
        "Monitor vital sign trends",
        "Observe for secondary symptoms"
    ]
    preliminary_tests = []
    medications = []

    # 1. Cardiac
    if any(x in combined for x in ["chest pain", "chest tightness", "chest discomfort", "crushing chest", "heart racing", "palpitations", "radiating to jaw", "radiating to arm"]):
        complexity = "High"
        rationale = "Potential Acute Coronary Syndrome (ACS) or myocardial infarction. High risk of cardiovascular events."
        criteria = [
            "12-Lead ECG changes (ST elevations, ST depressions, T-wave inversions)",
            "Serial troponin level trends (elevation indicates myocardial necrosis)",
            "Radiation of pain to jaw, neck, or left arm",
            "Hemodynamic stability (BP, HR, and perfusion state)"
        ]
        preliminary_tests = [
            "12-Lead ECG (perform within 10 minutes of arrival)",
            "Serial Cardiac Troponins (I or T)",
            "Chest X-Ray (CXR) to rule out aortic dissection or pneumothorax",
            "Coagulation panel (PT, INR, PTT)"
        ]
        medications = [
            {
                "name": "Aspirin (Chewable)",
                "dosage": "325 mg PO",
                "indication": "Suspected ACS / Myocardial Infarction",
                "warning": "Do not administer if patient has active GI bleeding, severe bleeding disorders, or aspirin allergy."
            },
            {
                "name": "Nitroglycerin (Sublingual)",
                "dosage": "0.4 mg q5min (max 3 doses)",
                "indication": "Active chest pain / anginal symptoms",
                "warning": "Avoid if systolic blood pressure is below 90 mmHg or if patient has taken PDE-5 inhibitors (e.g. Sildenafil) in the last 24-48 hours."
            }
        ]

    # 2. Respiratory
    elif any(x in combined for x in ["shortness of breath", "breathless", "difficulty breathing", "sob", "wheeze", "wheezing", "asthma", "copd"]):
        complexity = "High"
        rationale = "Risk of acute respiratory distress, asthma exacerbation, or COPD decompensation. Close respiratory monitoring required."
        criteria = [
            "Oxygen saturation (SpO2) stability (goal > 94%, or 88-92% for COPD)",
            "Work of breathing (use of accessory muscles, intercostal retractions, nasal flaring)",
            "Respiratory rate and breath sounds (wheezing, silent chest, stridor)",
            "Mental status changes (hypoxia/hypercapnia can induce confusion)"
        ]
        preliminary_tests = [
            "Continuous Pulse Oximetry",
            "Chest X-Ray (CXR)",
            "Arterial Blood Gas (ABG) if respiratory distress persists",
            "Complete Blood Count (CBC) to screen for underlying infection"
        ]
        medications = [
            {
                "name": "Albuterol (Nebulizer / Inhaler)",
                "dosage": "2.5 mg Nebulized or 2-4 puffs inhaler",
                "indication": "Bronchospasm / wheezing / asthma or COPD flare-up",
                "warning": "May cause tachycardia, tremors, or hypokalemia. Monitor heart rate."
            },
            {
                "name": "Methylprednisolone (IV)",
                "dosage": "40 - 125 mg IV",
                "indication": "Acute asthma / COPD systemic inflammation reduction",
                "warning": "Monitor blood glucose levels, particularly in diabetic patients."
            }
        ]

    # 3. Neurological / Stroke
    elif any(x in combined for x in ["slurred speech", "weakness", "stroke", "altered consciousness", "confusion", "confused", "unresponsive", "seizure", "fitting", "numbness"]):
        complexity = "High"
        rationale = "Suspected acute ischemic stroke, intracranial hemorrhage, or active seizure. Extremely time-critical pathway."
        criteria = [
            "FAST evaluation (Face drooping, Arm weakness, Speech difficulty, Time of onset)",
            "Glasgow Coma Scale (GCS) or AVPU score",
            "Pupillary response (size, symmetry, reactivity to light)",
            "Blood glucose level (rule out hypoglycemia mirroring stroke)"
        ]
        preliminary_tests = [
            "Non-contrast Head CT Scan (within 25 mins of arrival)",
            "Point-of-Care Blood Glucose",
            "Comprehensive Metabolic Panel (CMP) & Coagulation Panel",
            "Electroencephalogram (EEG) if persistent subclinical seizures suspected"
        ]
        medications = [
            {
                "name": "Alteplase (tPA) / Tenecteplase",
                "dosage": "Weight-based protocol (0.9 mg/kg for Alteplase)",
                "indication": "Acute Ischemic Stroke within 3 to 4.5 hours of Last Known Normal",
                "warning": "CRITICAL: Exclude hemorrhage via CT scan first. Absolute contraindications: active bleeding, head trauma, platelet count < 100k, anticoagulant use."
            },
            {
                "name": "Levetiracetam (Keppra)",
                "dosage": "500 - 1500 mg IV loading dose",
                "indication": "Active or recurring seizures",
                "warning": "Infuse slowly. Watch for somnolence, agitation, or acute behavioral changes."
            }
        ]

    # 4. Sepsis / Infection / Fever
    elif any(x in combined for x in ["sepsis", "fever", "high temperature", "chills", "lethargy", "infection", "uti"]):
        is_elderly = age and age >= 65
        is_pediatric = age and age < 18
        if is_elderly or is_pediatric:
            complexity = "High"
            rationale = "Fever or potential sepsis in vulnerable age extremes. High risk of rapid decompensation."
        else:
            complexity = "Medium"
            rationale = "Potential infection. Monitor for progression to systemic inflammatory response."
            
        criteria = [
            "qSOFA score (Respiratory rate >= 22, Altered mentation, Systolic BP <= 100)",
            "Core body temperature trends",
            "Hemodynamic stability and fluid responsiveness",
            "WBC and Lactate levels"
        ]
        preliminary_tests = [
            "Lactate level (serial monitoring if elevated)",
            "Blood Cultures (2 sets from different sites before antibiotics)",
            "Complete Blood Count (CBC) & Urinalysis with Culture",
            "C-Reactive Protein (CRP) / Procalcitonin"
        ]
        medications = [
            {
                "name": "Ceftriaxone (IV)",
                "dosage": "1 - 2 g IV q24h",
                "indication": "Broad-spectrum coverage for suspected bacterial infection / sepsis",
                "warning": "Verify penicillin/cephalosporin allergies. Avoid concurrent administration with calcium-containing IV solutions."
            },
            {
                "name": "Normal Saline / Lactated Ringer's",
                "dosage": "30 mL/kg IV bolus",
                "indication": "Hypotension / fluid resuscitation in sepsis",
                "warning": "Monitor volume status closely to avoid pulmonary edema, especially in patients with CHF or ESRD."
            }
        ]

    # 5. Allergic Reaction / Anaphylaxis
    elif any(x in combined for x in ["allergic", "allergy", "anaphylaxis", "rash", "hives", "swelling", "shellfish"]):
        if any(x in combined for x in ["difficulty breathing", "shortness of breath", "swelling", "face", "throat", "lip"]):
            complexity = "High"
            rationale = "Suspected severe systemic allergic reaction or anaphylaxis. Immediate risk of airway occlusion."
            criteria = [
                "Airway patency and occurrence of stridor/wheezing",
                "Hemodynamic status (anaphylactic shock leads to severe hypotension)",
                "Skin changes (progression of hives, angioedema)",
                "Respiratory effort and SpO2 levels"
            ]
            preliminary_tests = [
                "Continuous ECG and SpO2 monitoring",
                "Clinical airway assessment (have intubation equipment ready)"
            ]
            medications = [
                {
                    "name": "Epinephrine (1:1000)",
                    "dosage": "0.3 mg IM (in anterolateral thigh)",
                    "indication": "Anaphylaxis (respiratory distress, airway swelling, or hypotension)",
                    "warning": "Repeat every 5-15 mins if symptoms persist. Watch for severe anxiety, palpitations, or hypertensive crisis."
                },
                {
                    "name": "Diphenhydramine (Benadryl)",
                    "dosage": "25 - 50 mg IV/IM",
                    "indication": "Urticaria / pruritus associated with allergic reactions",
                    "warning": "Strong sedative properties. May cause hypotension if pushed too rapidly IV."
                }
            ]
        else:
            complexity = "Medium"
            rationale = "Localized allergic reaction. Low risk of systemic compromise, but monitor closely."
            criteria = [
                "Spread of rash or urticaria",
                "Monitor for onset of systemic symptoms (breathlessness, throat tightness)"
            ]
            preliminary_tests = ["Visual skin assessment", "Vital signs monitoring"]
            medications = [
                {
                    "name": "Cetirizine (Zyrtec)",
                    "dosage": "10 mg PO once daily",
                    "indication": "Mild allergic rash or itching",
                    "warning": "Generally non-drowsy but can cause mild somnolence in some patients."
                }
            ]

    # 6. Trauma / Bleeding / Injury
    elif any(x in combined for x in ["fall", "fracture", "laceration", "cut", "bleeding", "wound", "accident", "injury", "arm pain", "ankle"]):
        complexity = "Medium"
        rationale = "Acute physical trauma requiring structural evaluation, pain management, and bleeding/infection control."
        criteria = [
            "Neurovascular status distal to the injury (pulse, sensation, motor function)",
            "Active bleeding rate and control",
            "Deformity, joint range of motion, and weight-bearing capability",
            "Pain severity and control"
        ]
        preliminary_tests = [
            "Plain Radiography (X-Ray) of the affected extremity/area",
            "Tetanus immunization status check",
            "Complete Blood Count (CBC) if active bleeding is moderate/severe"
        ]
        medications = [
            {
                "name": "Ketorolac (Toradol)",
                "dosage": "15 - 30 mg IV/IM",
                "indication": "Moderate to severe acute musculoskeletal pain",
                "warning": "Contraindicated in renal impairment, active peptic ulcer disease, or suspected intracranial bleed. Do not use post-operatively if bleeding is a concern."
            },
            {
                "name": "Tetanus Toxoid Booster",
                "dosage": "0.5 mL IM",
                "indication": "Tetanus prophylaxis for contaminated or deep wounds",
                "warning": "Verify last vaccine date. Avoid if history of severe hypersensitivity reaction to tetanus vaccines."
            }
        ]

    # 7. Gastric / Abdominal Pain / Vomiting / Nausea
    elif any(x in combined for x in ["abdominal pain", "stomach pain", "nausea", "vomiting", "vomit"]):
        complexity = "Medium"
        rationale = "Evaluation needed for acute abdomen (appendicitis, cholecystitis, obstruction) or dehydration due to fluid loss."
        criteria = [
            "Abdominal tenderness (localized vs diffuse, rebound tenderness, guarding)",
            "Hydration status (mucous membranes, skin turgor, urine output, BP)",
            "Ability to tolerate oral intake",
            "Pain progression and changes in location (e.g. periumbilical to RLQ)"
        ]
        preliminary_tests = [
            "Abdominal Ultrasound or CT Abdomen/Pelvis",
            "Comprehensive Metabolic Panel (CMP) to monitor electrolytes and kidney function",
            "Lipase to rule out acute pancreatitis",
            "Urine Pregnancy Test (hCG) for females of childbearing age"
        ]
        medications = [
            {
                "name": "Ondansetron (Zofran)",
                "dosage": "4 mg IV or ODT (Orally Disintegrating Tablet)",
                "indication": "Severe nausea or active vomiting",
                "warning": "May prolong QT interval. Use with caution in patients at risk for arrhythmias."
            },
            {
                "name": "Lactated Ringer's / Normal Saline",
                "dosage": "1000 mL IV infusion",
                "indication": "Volume depletion and dehydration from fluid loss",
                "warning": "Monitor for fluid overload in patients with cardiac or renal dysfunction."
            }
        ]

    return {
        "complexity": complexity,
        "complexity_rationale": rationale,
        "criteria": criteria,
        "preliminary_tests": preliminary_tests,
        "medications": medications
    }
