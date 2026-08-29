from django.urls import path
from . import views

urlpatterns = [
    path('live/', views.live_queue),
    path('stats/', views.queue_stats),
    path('recompute/', views.recompute_queue),
]
