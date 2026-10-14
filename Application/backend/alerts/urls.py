from django.urls import path
from . import views

urlpatterns = [
    path('', views.alert_list),
    path('<uuid:alert_id>/acknowledge/', views.ack_alert),
]
