# PatientTriage.ai
> **An Intelligent, Resource-Aware Emergency Department (ED) Decision-Support System.**
> Developed as a simulated command-center prototype for Round 2 of the Accenture Innovation Challenge.

---

## 🌟 The Product Vision & Moat

### 1. The Core Product Principle: "AI Recommends. Clinicians Decide."
PatientTriage.ai acts as a safety-first clinician co-pilot, not an autonomous agent. 
- **Explainable Severity Levels**: Every patient is scored into priority levels **P1 (Immediate) to P5 (Non-Urgent)**.
- **Unalterable Auditing**: Any clinician override of the AI's triage assessment requires a documented clinical justification, which is written to a tamper-proof event audit log (`AuditEvent`).

### 2. Waiting-Patient Re-Triage (The Starvation Prevention Moat)
In typical EDs, low-priority patients can wait indefinitely if critical cases keep arriving. PatientTriage.ai implements an **OS-inspired dynamic scheduling pipeline**:
- **Priority Aging**: Patients waiting in the queue have their triage priority score incremented dynamically over time based on their individual **degradation rate**.
- **Continuous Monitoring**: If new vitals or note updates suggest clinical degradation, the system triggers instant WebSocket alerts, and re-triages them immediately.

### 3. Dynamic Inpatient Observation Sequence
Instead of treating "Admission" as a simple binary completed status, our care sequence tracks patients through their inpatient transfer:
- **Seen Stage**: Clinicians attend to active visits and decide to Admit, Refer, or Discharge.
- **Observation (Admitted) Stage**: Admitting a patient transitions their status to `admitted`, moves them to the **Observation** step, and assigns them to an ED observation bed resource. Their triage priority is automatically changed to `P5` to reflect their stabilized state, and the assigned doctor is instantly freed to take other patients.
- **Resource Release**: Clinicians can discharge or refer patients directly from the new Observation tab, freeing up the observation bed resource.

### 4. Interactive DOM-Based Auto-Play Simulation
To simplify clinical walkthroughs, the system features a visual **Auto-Play Simulation Mode**:
- **Simulated Pointer Cursor**: A floating mouse cursor types into inputs and clicks buttons to demonstrate a realistic clinical workflow.
- **Context-Aware Tab Switching**: The system automatically switches views to the relevant tabs (e.g. `Vitals Pending` when entering vital signs, `Tests Suggested` when completing scans) as the cursor acts.
- **Mock Dialog Bypass**: Browser prompt and confirmation dialogues are temporarily mocked during Auto-Play, ensuring the simulation proceeds without blocking popup alerts.

<<<<<<< HEAD
### 5. Resilient Offline RAG Fallback & Gemini Bypass
To prevent system freezes during network timeouts:
- **Local RAG Fallback**: If the Gemini API is offline or returns rate limit errors, the system falls back to a local RAG Knowledge Store, executing diagnostic logic instantly (<100ms).
- **Gemini Bypass**: Setting `BYPASS_GEMINI_API=true` in `.env` disables external network attempts, preventing the default 25-second HTTP request blocking.

---

## 🧠 Clinical Intelligence & Rules

### 1. Age-Specific Clinical Interpretation
Triage recommendations are adjusted for different age groups:
- **Pediatrics**: Higher resting heart and respiratory rates are normalized, while high fevers are flagged with higher risk triggers.
- **Geriatrics**: High blood pressure or mild confusion are prioritized heavily due to higher baseline stroke and myocardial infarction risks.

### 2. Uncertainty & Confidence Scoring
If clinical fields (like SpO2 or respiratory rate) are missing, the system does not silently downgrade patient risk. Instead, it lowers the AI's confidence rating and raises a **"Review Required"** flag, prompting human-in-the-loop validation.

### 3. Dynamic Triage Thresholds
During surge events (activated via **3× Surge**), the system automatically adjusts triage thresholds to optimize patient flow and resource utilization.

---

## 🔄 Internal Application Features & User Flows

### 1. Resource Mapping & Capacity Tracking
The system models clinical and personnel resources as finite cores to accurately represent ED constraints:
* **observation_bed (Observation Beds)**: Allocated to admitted patients during their transition/observation stay.
* **resus_bay (Resuscitation Bays)**: Reserved for high-urgency patients (**P1/P2**).
* **treatment_room (Adult Treatment Rooms)**: Occupied by standard adult patients (**P3/P4**) during active clinician visits.
* **fast_track_room (Pediatric Fast-Track Rooms)**: Dedicated to pediatric patients to expedite child care flows.
* **Clinician Staff (Doctor Cores)**: Named doctor cores (e.g. Dr. Kapoor, Dr. Sharma, Dr. Roy) with specialized department capability tags (General Medicine, Cardiac Care, Pediatrics, Orthopedics, and Resuscitation).

### 2. Vital Signs Parameters & Feasible Limits
Incoming vitals are strictly validated against biological and feasible limits:
* **Oxygen Saturation (SpO₂)**: Must be between `50%` and `100%`. Feasible limits strictly block values outside this range (e.g. `<50%` or `>100%`) with clear validation errors.
* **Heart Rate (HR)**: Validated between `30 bpm` and `220 bpm`.
* **Blood Pressure (BP)**: Systolic validated between `50 mmHg` and `250 mmHg`; Diastolic between `30` and `150 mmHg`.
* **Respiratory Rate (RR)**: Validated between `8 rpm` and `60 rpm`.
* **Temperature**: Validated between `34°C` and `42°C` (`93.2°F` to `107.6°F`).

---

### 3. Scenario-Based User Flows

```mermaid
flowchart TD
    A[Patient Intake] --> B{Standard ID?}
    B -- No --> C[Register TEMP ID]
    B -- Yes --> D[Link ABHA Profile]
    C --> E[Vitals Recorded]
    D --> E
    E --> F[AI Triage Recommendation]
    F --> G{Scans Recommended?}
    G -- Yes --> H[Mark Under Scan]
    H --> I[Complete Scan Reports]
    I --> J[Active Doctor Visit]
    G -- No --> J
    J --> K{Clinician Override?}
    K -- Yes --> L[Log Override Reason]
    K -- No --> M[Make Disposition Decision]
    L --> M
    M --> N{Disposition Type?}
    N -- Admit --> O[Observation Bed P5]
    N -- Discharge/Refer --> P[Release ED Resources]
    O --> Q[Discharge from Obs]
    Q --> P
=======
## Repository Structure
```text
backend/
frontend/
>>>>>>> ec2ef1d3db56b4c6feb21f820d05317d0aa19df8
```

#### Scenario A: Zero-History & Identity Resolution
1. **Intake Registration**: A patient enters the ED without identification. The intake nurse registers them, creating a temporary profile (e.g. `TEMP-9821`) with no historical notes.
2. **First Triage**: Vitals are recorded. Since medical history is unavailable, the AI's confidence rating drops, and the system raises a "Review Required" warning flag.
3. **Identifier Matching**: The clinician retrieves a standard ABHA ID (e.g. `ABHA-4221-5582`) and performs a lookup resolution.
4. **Automated Merging**: The system links the standard profile, merges past medical notes, and automatically triggers re-triage, updating the patient’s risk category based on newly incorporated medical histories.

#### Scenario B: Triage & Clinical Degradation Alerting
1. **Queue Positioning**: A stable patient is assigned a **P3 (Urgent)** triage badge and waits in the queue.
2. **Priority Aging**: As wait time increases, the OS scheduler periodically increments the patient's dynamic score.
3. **Vital Degradation**: The triage nurse updates the patient's vitals (e.g. SpO2 drops to `90%`, Heart Rate rises).
4. **WebSocket Alarm**: The backend detects degradation and pushes an immediate alert to all dashboards. The patient row flashes red and moves to the top of the waitlist.

#### Scenario C: Diagnostics & Scan Ordering Flow
1. **Triage Recommendation**: The AI assessment recommends diagnostic testing (e.g. *Chest X-Ray* or *Troponins*).
2. **Start Scan**: The technician clicks **Mark as Under Scan**, moving the patient to the "Scan" tab.
3. **Tech Submission**: The technician clicks **Complete Scan**. A modal opens; the tech inputs reports or clicks auto-generate (which skips confirmation popups when Auto-Play is active).
4. **Re-Triage Boost**: The scan completes, applying an I/O priority boost to the patient's score so they are prioritized for doctor allocation.

#### Scenario D: Doctor Assignment & Clinician Override
1. **Core Allocation**: The scheduler finds a free doctor matching the patient's department and assigns them.
2. **Start Visit**: The doctor initiates the consultation, transitioning the patient status to `in_progress` (Seen tab).
3. **Clinical Override**: The doctor disagrees with the AI's P2 severity recommendation. They click the **Override** button.
4. **Justification Logging**: The doctor downgrades the priority to P3, inputs a clinical justification, and saves. The system registers the override in the audit logs.

#### Scenario E: Inpatient Admission & Bed Transition
1. **Disposition Selection**: The doctor decides the patient requires inpatient monitoring and clicks **Admit**.
2. **ED Core Release**: The patient's status becomes `admitted`, their assigned doctor is freed to take new patients, and their priority changes to `P5` (observation bed/low urgency).
3. **Ward Observation**: The patient moves to the Observation tab, occupying an observation bed.
4. **ED Exit**: Once a ward bed is ready, the coordinator clicks **Discharge** from the Observation actions list. The observation bed is released, completing the patient care sequence.

---

## 🛠 Technical Architecture & Stack

### Backend (Django + Channels)
- **Django REST Framework**: Implements clean, typed API contracts.
- **Django Channels & WebSockets**: Pushes real-time alerts, priority updates, and surge events to all connected clients.
- **Database**: PostgreSQL (or SQLite for local development) with deterministic seeder configurations.

### Frontend (React + Vite + Tailwind CSS)
- **State Management**: Zustand global store.
- **Vitals Trend Chart**: Interactive charting displaying historical vital trends.
- **Responsive Layout**: Designed to render without vertical or horizontal text truncation at 100% zoom.

---

## 📂 Repository Structure

```text
├── backend/
│   ├── config/              # Django settings & URL routing
│   ├── patients/            # Models (Patient, VitalReading), views, and serializers
│   ├── triage/              # Clinical assessment and re-triage services
│   ├── routing/             # Resource allocation (doctor cores, beds) and scheduler
│   ├── simulation/          # Seeder profiles, surge logic, and simulator views
│   └── .env                 # Environment variables
└── frontend/
    ├── src/
    │   ├── components/      # steppers, charts, simulation controls
    │   ├── pages/           # CommandCenter Dashboard, PatientDetail
    │   ├── store.js         # Zustand store for state sharing
    │   └── workflow.js      # ED Care Sequence pipeline logic
```

---

## 🚀 Setup & Installation

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure your `.env` file (save inside the `backend/` folder):
   ```ini
   DEBUG=True
   SECRET_KEY=local-secret-key-123
   BYPASS_GEMINI_API=True
   GEMINI_API_KEY=your_key_here
   ```
5. Apply database migrations:
   ```bash
   python manage.py migrate
   ```
6. Run the server:
   ```bash
   python manage.py runserver
   ```

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd ../frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```
4. Access the command center at `http://localhost:5173`.

---

## How to Operate the Application

### 1. The Simulation Control Panel (Left Sidebar)
This sidebar manages the simulation's state machine, timeline ticks, and automated visual walkthroughs:
* **Start (Seed)**: Resets the database and seeds **15–20** realistic, age-specific baseline patients (pediatric, adult, and geriatric). The queue tab automatically switches to *Vitals Pending* to guide your next action.
* **Manual Intake**: Manually adds the next patient from the synthetic queue files.
* **3× Surge**: Instantly triggers a surge event, adding **10** high-severity patients in a spike. This disables automatically once clicked to prevent duplicate profiles.
* **Start Auto-Play**: Toggles the visual DOM cursor overlay. The simulated mouse cursor will perform patient registrations, fill forms, submit scans, and tick scheduler stages automatically.
* **Reset**: Clears all patients, clinical reports, and event logs from the database, returning the command center to a blank state.
* **Vertical Stage Stepper**: Displays the active pipeline stage (`Triage Reassess`, `Scan Completion`, `Priority Aging`, or `Doctor Allocation`). When Auto-Play is active, the cursor focuses on these stages as ticks occur.

---

### 2. The Patient Board Grid (Main Dashboard)
The dashboard displays the active patients in the ED, divided into workflow status tabs:
* **All Tab**: Displays all patients currently in the ED (waiting, in visit, or admitted).
* **Critical (P1/P2) Tab**: Focuses on highest-severity emergencies.
* **Vitals Pending Tab**: Displays patients requiring vital signs entries. Click the **Record Vitals** button on a patient row to pre-fill vitals and trigger AI triage.
* **Suggested Scans Tab**: Displays patients requiring diagnostic imaging. 
  * Click **Check Recommended Scans** to open the solid scans modal overlay.
  * Click **Mark as Under Scan** to start the diagnostic cycle.
  * Click **Complete Scan** to submit reports (or mock prompt bypasses when Auto-Play is active).
* **In Queue Tab**: Patients who are triaged and waiting for clinician allocation. Click **Start Visit** to assign them to a doctor core manually.
* **Seen (In Progress) Tab**: Patients undergoing doctor visits. Click **Admit**, **Refer**, or **Discharge** to decide their disposition.
* **Observation (Admitted) Tab**: Patients occupying ED observation beds. Click **Discharge** or **Refer** to release their observation beds.
* **Discharged / Referred (Completed) Tab**: Historical log of completed dispositions.

---

### 3. Patient Details Page (`/patient/:id`)
Clicking any patient row navigates you to their clinical file view:
* **Contextual Action Bar (Top Right)**: Rendered dynamically based on care sequence stages:
  * **Start Visit**: Moves the patient to active doctor consults.
  * **Admit / Refer / Discharge**: Disposition actions that update status and release active resources.
* **Clinician Override Button**: Next to the priority badges. Click **Override**, choose a new severity level (P1-P5), enter a clinical justification, and save to update the triage ranking.
* **Vitals Trend Chart**: Graph displays trends for heart rate, blood pressure, SpO₂ (Oxygen Saturation, validated between `50%` and `100%`), and temperature over time.
* **Clinical Notes & CDS Explainer**: Left column displays AI triage logic explanations, symptom triggers, and missing vital alerts.
* **Vitals & Notes Forms**: Use form fields at the bottom to append new clinical notes or vital measurements manually.

---

## Recommended Demonstration Scenario

1. **Seed Baseline**: Open the dashboard and click the **Seed** button. You'll see 15–20 synthetic patients populated with age-specific clinical profiles.
2. **Start Auto-Play**: Click the **Start Auto-Play** toggle in the sidebar. Watch the simulated mouse cursor perform patient intake, fill out vitals forms, trigger scans, and assign doctors.
3. **Observe Re-Triage**: Keep an eye on the *Deteriorating* section. Patients whose vitals degrade are highlighted in red and automatically re-triaged with a higher priority badge.
4. **Trigger 3× Surge**: Click the **3× Surge** button. Ten additional critical and complex patients arrive in a spike. Observe the bed occupancy rate on the status ribbon increase, and notice that the Surge button disables to prevent accidental duplicates.
5. **Disposition & Bed Release**: Navigate to the details page of an admitted patient. Click **Discharge** from the action bar; note that the patient completes their care flow and their observation bed is instantly released.
6. **Inspect Logs**: Visit the **Audit Logs** tab to view the unalterable history of system assessments and manual overrides.
