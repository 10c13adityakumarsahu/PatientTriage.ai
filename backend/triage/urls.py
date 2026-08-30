from django.urls import path
from . import views
from patients.views import patient_detail  # reuse for assessment history

urlpatterns = [
    path('assess/', views.assess),
    path('reassess/', views.reassess),
    path('ai-analyze/', views.ai_analyze_symptoms),
    path('ai-mode/', views.ai_mode_status_view),
]
