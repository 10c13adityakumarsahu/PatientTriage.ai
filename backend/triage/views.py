"""Triage views — assess and reassess endpoints."""
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from patients.models import Patient
from .models import RiskAssessment
from .serializers import RiskAssessmentSerializer
from .services import run_triage_assessment


@api_view(['POST'])
def assess(request):
    """POST /triage/assess/ — Initial assessment for a patient."""
    patient_id = request.data.get('patient_id')
    if not patient_id:
        return Response({'error': 'patient_id required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

    assessment = run_triage_assessment(patient, trigger='initial_assessment')
    return Response(RiskAssessmentSerializer(assessment).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def reassess(request):
    """POST /triage/reassess/ — Re-assessment for a patient."""
    patient_id = request.data.get('patient_id')
    trigger = request.data.get('trigger', 'manual_reassessment')

    if not patient_id:
        return Response({'error': 'patient_id required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

    assessment = run_triage_assessment(patient, trigger=trigger)
    return Response(RiskAssessmentSerializer(assessment).data, status=status.HTTP_200_OK)


@api_view(['GET'])
def assessment_history(request, patient_id):
    """GET /patients/{patient_id}/assessments/ — Full assessment history."""
    assessments = RiskAssessment.objects.filter(patient_id=patient_id).order_by('-created_at')
    return Response(RiskAssessmentSerializer(assessments, many=True).data)


@api_view(['POST'])
def ai_analyze_symptoms(request):
    """POST /triage/ai-analyze/ — on-the-fly symptom analysis before patient registration."""
    chief_complaint = request.data.get('chief_complaint', '')
    relevant_history = request.data.get('relevant_history', '')
    age = request.data.get('age')
    sex = request.data.get('sex', '')

    if age is not None:
        try:
            age = int(age)
        except ValueError:
            age = None

    from decision_engine.ai_assistant import analyze_symptoms_ai
    result = analyze_symptoms_ai(
        chief_complaint=chief_complaint,
        relevant_history=relevant_history,
        age=age,
        sex=sex
    )
    return Response(result, status=status.HTTP_200_OK)
