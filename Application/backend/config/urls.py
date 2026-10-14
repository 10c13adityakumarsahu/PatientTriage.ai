"""Main URL configuration for PatientTriage.ai API."""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include([
        path('patients/', include('patients.urls')),
        path('patients/<uuid:patient_id>/assessments/', include('triage.assessment_urls')),
        path('patients/<uuid:patient_id>/override/', include('overrides.patient_urls')),
        path('triage/', include('triage.urls')),
        path('queues/', include('queues.urls')),
        path('routing/', include('routing.urls')),
        path('alerts/', include('alerts.urls')),
        path('overrides/', include('overrides.urls')),
        path('audit/', include('audit.urls')),
        path('simulation/', include('simulation.urls')),
    ])),
]
