"""Routing serializers and views."""
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import Resource, RoutingRecommendation
from patients.models import Patient
from triage.services import run_triage_assessment


class ResourceSerializer(serializers.ModelSerializer):
    available_slots = serializers.ReadOnlyField()
    utilization_pct = serializers.ReadOnlyField()

    class Meta:
        model = Resource
        fields = [
            'id', 'name', 'resource_type', 'capacity',
            'occupied', 'available_slots', 'utilization_pct',
            'capabilities', 'status', 'updated_at'
        ]


class RoutingRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoutingRecommendation
        fields = ['id', 'patient_id', 'destination', 'rationale', 'confidence', 'accepted', 'created_at']


@api_view(['GET', 'POST'])
def resource_list(request):
    if request.method == 'GET':
        resources = Resource.objects.all()
        return Response(ResourceSerializer(resources, many=True).data)
    elif request.method == 'POST':
        ser = ResourceSerializer(data=request.data)
        if ser.is_valid():
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH', 'DELETE'])
def resource_detail(request, resource_id):
    try:
        res = Resource.objects.get(id=resource_id)
    except Resource.DoesNotExist:
        return Response({'error': 'Resource not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'PATCH':
        ser = ResourceSerializer(res, data=request.data, partial=True)
        if ser.is_valid():
            ser.save()
            return Response(ser.data)
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
    elif request.method == 'DELETE':
        res.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
def patient_routing(request, patient_id):
    rec = RoutingRecommendation.objects.filter(patient_id=patient_id).order_by('-created_at').first()
    if not rec:
        return Response({'error': 'No routing recommendation'}, status=status.HTTP_404_NOT_FOUND)
    return Response(RoutingRecommendationSerializer(rec).data)


@api_view(['POST'])
def recommend_routing(request, patient_id):
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

    assessment = run_triage_assessment(patient, trigger='routing_recompute')

    # Get or create routing recommendation
    resources = [
        {
            'resource_type': r.resource_type,
            'available_slots': r.available_slots,
            'status': r.status,
        }
        for r in Resource.objects.all()
    ]
    from decision_engine.routing_engine import recommend_destination
    destination, rationale, confidence = recommend_destination(
        assessment.priority, resources
    )

    rec = RoutingRecommendation.objects.create(
        patient=patient,
        destination=destination,
        rationale=rationale,
        confidence=confidence,
    )

    from simulation.broadcast import broadcast_event
    broadcast_event('resource.updated', ResourceSerializer(Resource.objects.all(), many=True).data)

    return Response(RoutingRecommendationSerializer(rec).data, status=status.HTTP_201_CREATED)
