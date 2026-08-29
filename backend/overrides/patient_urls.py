"""Patient-specific override URL."""
from django.urls import path
from overrides.views import create_override

urlpatterns = [
    path('', create_override),
]
