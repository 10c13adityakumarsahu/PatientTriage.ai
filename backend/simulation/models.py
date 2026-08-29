"""Simulation state model."""
import uuid
from django.db import models


class SimulationState(models.Model):
    """Singleton-ish simulation state tracker."""
    scenario_name = models.CharField(max_length=100, default='baseline')
    surge_active = models.BooleanField(default=False)
    sim_time = models.DateTimeField(null=True, blank=True)
    seed = models.IntegerField(default=42)
    is_running = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"SimulationState[{self.scenario_name}] surge={self.surge_active}"
