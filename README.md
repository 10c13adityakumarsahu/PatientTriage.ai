# PatientTriage.ai

> **A dynamic priority queue that understands risk.**

PatientTriage.ai is a simulated emergency-department AI decision-support prototype developed for the Accenture Innovation Challenge Round 2.

## What It Demonstrates
- Rapid AI-assisted intake
- Explainable risk/severity recommendation
- Explicit confidence and uncertainty
- Dynamic priority queues
- Continuous waiting-patient monitoring
- Deterioration-driven re-triage
- Resource-aware routing
- Clinician override
- Auditability
- 3× surge simulation

## Product Principle
**AI recommends. Humans decide.**

## Important Notice
This repository is a prototype using synthetic/illustrative data. It is not clinically validated and must not be used to make real patient-care decisions.

## Stack
- React + TypeScript + Vite
- Tailwind + shadcn/ui
- Django + Django REST Framework
- PostgreSQL
- Django Channels
- Python decision engine
- Redis/Celery where required for simulation

## Repository Structure
```text
backend/
frontend/
data/
AGENTS.md
PRODUCT.md
DOMAIN.md
DECISION_ENGINE.md
SAFETY.md
DATA_MODEL.md
API_SPEC.md
UX_SPEC.md
SIMULATION.md
EVALUATION.md
ARCHITECTURE.md
ROADMAP.md
```

## Core Flow
```text
Sense → Assess → Prioritize → Route → Monitor → Re-prioritize
```

## Demo Scenario
1. Start baseline scenario.
2. Open live queue.
3. Select a patient and inspect AI recommendation.
4. Trigger deterioration.
5. Observe priority change and alert.
6. Open clinician decision panel.
7. Override the recommendation.
8. Open audit trail.
9. Reset and run 3× surge.

## Development
Detailed setup commands belong here once the project scaffolding is created. Keep setup instructions executable and tested.

## Evidence
The Round 2 challenge brief asks for a working prototype on realistic/simplified data and specifically expects 15–20 simulated patients, an ambiguous case, pediatric/geriatric case, zero-history case, 3× surge, explicit confidence, and a clinician override with logging.
