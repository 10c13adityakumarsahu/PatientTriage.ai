from django.test import TestCase
from rest_framework.test import APIClient
from django.utils import timezone
from patients.models import Patient
from triage.models import RiskAssessment

class PatientIntakeAITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.patient = Patient.objects.create(
            name="Test Patient",
            patient_identifier="ABHA-1234-5678",
            age=45,
            sex="M",
            arrival_time=timezone.now(),
            chief_complaint="moderate chest pain",
            relevant_history="Hypertension",
            status="waiting"
        )
        # Create an assessment to simulate history
        self.assessment = RiskAssessment.objects.create(
            patient=self.patient,
            priority="P2",
            confidence=0.85,
            risk_factors=["Chest pain"],
            recommended_destination="cardiac_care",
            trigger="initial_assessment"
        )

    def test_patient_lookup_existing(self):
        response = self.client.get('/api/v1/patients/lookup/', {'identifier': 'ABHA-1234-5678'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['exists'])
        self.assertEqual(response.data['demographics']['name'], "Test Patient")
        self.assertEqual(len(response.data['past_records']), 1)
        self.assertEqual(response.data['past_records'][0]['chief_complaint'], "moderate chest pain")

    def test_patient_lookup_nonexistent(self):
        response = self.client.get('/api/v1/patients/lookup/', {'identifier': 'ABHA-0000-1111'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['exists'])

    def test_ai_analyze_symptoms(self):
        payload = {
            'chief_complaint': 'severe chest pain radiating to jaw',
            'relevant_history': 'Smoker, diabetes',
            'age': 60,
            'sex': 'M'
        }
        response = self.client.post('/api/v1/triage/ai-analyze/', payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['complexity'], 'High')
        self.assertTrue(any("ECG" in test for test in response.data['preliminary_tests']))
        self.assertTrue(any("Aspirin" in med['name'] for med in response.data['medications']))

    def test_identity_resolution_flow(self):
        # Create a patient with a temporary ID
        temp_patient = Patient.objects.create(
            name="Emergency Patient (Temp)",
            patient_identifier="TEMP-998877",
            age=30,
            sex="F",
            arrival_time=timezone.now(),
            chief_complaint="moderate wheezing",
            status="waiting"
        )
        # Create initial triage assessment
        from triage.services import run_triage_assessment
        run_triage_assessment(temp_patient, trigger='initial_assessment')
        
        # Patch the temporary patient's ID to match the existing standard ID
        payload = {
            'patient_identifier': 'ABHA-1234-5678',
            'name': 'Test Patient',
            'relevant_history': 'Hypertension'
        }
        
        response = self.client.patch(f'/api/v1/patients/{temp_patient.id}/', payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['patient_identifier'], 'ABHA-1234-5678')
        self.assertEqual(response.data['name'], 'Test Patient')
        
        # Verify that triage reassessment was triggered on resolution
        temp_patient.refresh_from_db()
        self.assertEqual(temp_patient.relevant_history, 'Hypertension')
        self.assertTrue(temp_patient.assessments.filter(trigger='identity_resolved').exists())

