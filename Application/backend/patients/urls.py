"""Patients URL configuration."""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.patient_list_create),
    path('lookup/', views.patient_lookup),
    path('<uuid:patient_id>/', views.patient_detail),
    path('<uuid:patient_id>/vitals/', views.add_vitals),
    path('<uuid:patient_id>/observations/', views.add_observation),
    path('<uuid:patient_id>/mark-under-scan/', views.mark_under_scan),
    path('<uuid:patient_id>/submit-scan-reports/', views.submit_scan_reports),
]
