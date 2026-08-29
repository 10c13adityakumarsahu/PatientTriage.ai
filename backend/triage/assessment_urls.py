"""Assessment history URL for patients sub-resource."""
from django.urls import path
from triage.views import assessment_history

urlpatterns = [
    path('', assessment_history),
]
