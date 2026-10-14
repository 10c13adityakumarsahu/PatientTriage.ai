from django.urls import path
from . import views

urlpatterns = [
    path('seed/', views.seed),
    path('tick/', views.tick),
    path('deteriorate/', views.deteriorate),
    path('surge/', views.surge),
    path('reset/', views.reset),
    path('status/', views.sim_status),
    path('intake-next/', views.intake_next),
    path('next-patient-data/', views.next_patient_data),
]
