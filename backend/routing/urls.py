from django.urls import path
from . import views

urlpatterns = [
    path('resources/', views.resource_list),
    path('resources/<uuid:resource_id>/', views.resource_detail),
    path('patients/<uuid:patient_id>/routing/', views.patient_routing),
    path('patients/<uuid:patient_id>/routing/recommend/', views.recommend_routing),
]
