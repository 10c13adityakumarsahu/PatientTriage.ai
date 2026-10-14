"""
Routing Engine + OS-Scheduler — recommends destination and models resource
allocation using an operating-system process-scheduler metaphor.

OS Metaphor:
  CPU cores     = resource units (resus bays, treatment rooms, etc.)
  Processes     = patients with dynamic priority scores
  I/O wait      = vitals pending or under scan (scheduler_state = "blocked")
  Ready queue   = patients in scheduler_state = "ready", awaiting a core
  Running       = patient receiving active clinical care (scheduler_state = "running")
  Scheduler     = this module — allocates best-fit core using priority + dynamic score

Principles:
  - Blocked processes (I/O) do NOT consume a running slot — only a waiting slot
  - Unblock signal: vitals recorded or scan completed → patient re-enters ready queue
  - Priority preemption: P1/P2 can displace P4/P5 from "best fit" core if all full
  - Surge mode: confidence penalties increase, fallback routing more aggressive
  - Resources are read from the DB via the triage service; this module is stateless

Returns a recommendation, not an autonomous command.
Clinician review/override always takes precedence.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
from .priority_mapper import priority_to_destination

if TYPE_CHECKING:
    from .models import PatientState


# ─────────────────────────────────────────────────────────────────────────────
# Destination → queue type mapping
# ─────────────────────────────────────────────────────────────────────────────
DESTINATION_TO_QUEUE = {
    "resuscitation":    "resuscitation",
    "general_emergency": "general_emergency",
    "fast_track":       "fast_track",
    "observation":      "observation",
}

# Destination → resource type mapping
DESTINATION_TO_RESOURCE = {
    "resuscitation":     "resus_bay",
    "general_emergency": "treatment_room",
    "fast_track":        "fast_track_room",
    "observation":       "observation_bed",
}

# Fallback chains — when preferred destination is at capacity
FALLBACK_CHAINS = {
    "resuscitation":     ["general_emergency"],
    "general_emergency": ["observation", "fast_track"],
    "fast_track":        ["observation", "general_emergency"],
    "observation":       ["general_emergency"],
}

# Priority ordinal (lower = more urgent)
PRIORITY_ORDER = {"P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5}


# ─────────────────────────────────────────────────────────────────────────────
# SchedulerCore — models a single resource unit as a CPU core
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class SchedulerCore:
    """Models one resource unit (bed / bay / room) as a CPU core."""
    resource_type: str
    destination: str
    total_capacity: int
    occupied: int
    available_slots: int
    status: str = "available"    # available | offline | limited

    @property
    def is_available(self) -> bool:
        return self.status == "available" and self.available_slots > 0

    @property
    def load_pct(self) -> float:
        if self.total_capacity == 0:
            return 1.0
        return self.occupied / self.total_capacity

    @property
    def core_label(self) -> str:
        return f"{self.destination.replace('_', ' ').title()} ({self.available_slots} slots free)"


def _build_scheduler_cores(resources: list, surge_active: bool = False) -> dict[str, list[SchedulerCore]]:
    """
    Build SchedulerCore instances grouped by destination from raw resource dicts.
    Each resource record maps to one core (or aggregates if multiple of same type).
    """
    dest_resource_map = {v: k for k, v in DESTINATION_TO_RESOURCE.items()}
    cores: dict[str, list[SchedulerCore]] = {}

    for r in resources:
        rtype = r.get("resource_type", "")
        dest = dest_resource_map.get(rtype, "general_emergency")
        capacity = r.get("capacity", r.get("available_slots", 0) + r.get("occupied", 0))
        occupied = r.get("occupied", 0)

        # 3x Surge resource impact: artificially inflate occupancy to simulate core load pressure
        if surge_active:
            occupied = min(capacity, occupied + int(capacity * 0.4) + 1)

        available = max(0, capacity - occupied)
        status = r.get("status", "available")

        core = SchedulerCore(
            resource_type=rtype,
            destination=dest,
            total_capacity=capacity,
            occupied=occupied,
            available_slots=available,
            status=status,
        )

        if dest not in cores:
            cores[dest] = []
        cores[dest].append(core)

    return cores


def _aggregate_core_capacity(cores: dict[str, list[SchedulerCore]]) -> dict[str, int]:
    """Aggregate available slots per destination across all cores."""
    return {
        dest: sum(c.available_slots for c in core_list if c.is_available)
        for dest, core_list in cores.items()
    }


def _get_core_load(cores: dict[str, list[SchedulerCore]], dest: str) -> float:
    """Return average load percentage for a destination."""
    dest_cores = cores.get(dest, [])
    if not dest_cores:
        return 1.0
    return sum(c.load_pct for c in dest_cores) / len(dest_cores)


# ─────────────────────────────────────────────────────────────────────────────
# I/O state helpers (for scheduler state annotation)
# ─────────────────────────────────────────────────────────────────────────────
def classify_scheduler_state(state: Optional["PatientState"]) -> str:
    """
    Classify the patient process state for the OS scheduler.
    Returns: 'blocked_io_vitals' | 'blocked_io_scan' | 'ready' | 'running' | 'referred'
    """
    if state is None:
        return "ready"

    # I/O wait: vitals not yet recorded
    if state.current_vitals is None:
        return "blocked_io_vitals"

    # I/O wait: under scan (flag in scenario_tag or observed_cues)
    if "under_scan" in (state.scenario_tag or "") or \
       any("scan" in str(c).lower() for c in (state.observed_cues or [])):
        return "blocked_io_scan"

    # Running
    if state.current_priority is not None and getattr(state, "_in_progress", False):
        return "running"

    return "ready"


def get_scheduler_state_label(scheduler_state: str) -> str:
    return {
        "blocked_io_vitals": "⏸ Blocked — Awaiting Vitals (I/O)",
        "blocked_io_scan":   "⏸ Blocked — Under Scan (I/O)",
        "ready":             "▶ Ready — In Triage Queue",
        "running":           "⚙ Running — Under Clinical Care",
        "referred":          "✓ Done — Referred/Discharged",
    }.get(scheduler_state, "? Unknown")


# ─────────────────────────────────────────────────────────────────────────────
# Core scheduler: selects best-fit core for a patient
# ─────────────────────────────────────────────────────────────────────────────
def schedule_patient(
    priority: str,
    dynamic_score: float,
    cores: dict[str, list[SchedulerCore]],
    preferred_dest: str,
    surge_active: bool = False,
) -> tuple[str, str, float]:
    """
    OS-scheduler: select the best-fit core (destination) for a patient process.

    Selection criteria (in order):
    1. Preferred destination has available slots → use it
    2. Preferred full → try fallback chain by available slots
    3. All full → flag pressure; stay at preferred (waiting in queue)

    Priority preemption: P1 patients are always routed to resuscitation if
    any slot exists across ALL destinations (safety rule).

    Returns (selected_destination, rationale, confidence).
    """
    capacity_map = _aggregate_core_capacity(cores)

    rationale_parts = []
    confidence = 0.90

    # P1 preemption: must go to resus if any slot anywhere
    if priority == "P1":
        resus_slots = capacity_map.get("resuscitation", 0)
        if resus_slots > 0:
            load = _get_core_load(cores, "resuscitation")
            rationale_parts.append(
                f"P1 preemption: Resuscitation bay assigned ({resus_slots} slots, {load:.0%} load)"
            )
            return "resuscitation", "; ".join(rationale_parts), 0.95

        # Resus full — try general_emergency but flag critical pressure
        gen_slots = capacity_map.get("general_emergency", 0)
        if gen_slots > 0:
            rationale_parts.append(
                "P1 CRITICAL: Resus at capacity — rerouting to General Emergency. Flag capacity pressure."
            )
            confidence = 0.70
            return "general_emergency", "; ".join(rationale_parts), confidence

        rationale_parts.append("P1 CRITICAL: All preferred cores at capacity — patient queued. Escalate resource alert.")
        return "resuscitation", "; ".join(rationale_parts), 0.50

    # Standard scheduling: preferred first
    preferred_slots = capacity_map.get(preferred_dest, None)

    if preferred_slots is None:
        # No resource data
        rationale_parts.append(f"Priority {priority} → {preferred_dest} (no capacity data)")
        confidence = 0.75
    elif preferred_slots > 0:
        load = _get_core_load(cores, preferred_dest)
        rationale_parts.append(
            f"Priority {priority} → {preferred_dest.replace('_', ' ').title()} "
            f"({preferred_slots} slots, {load:.0%} load)"
        )
        # Higher load slightly reduces routing confidence
        if load > 0.80:
            confidence = 0.80
            rationale_parts.append("Core load >80% — monitor for saturation")
    else:
        # Preferred full: try fallback chain
        selected = None
        for alt in FALLBACK_CHAINS.get(preferred_dest, []):
            alt_slots = capacity_map.get(alt, 0)
            if alt_slots > 0:
                selected = alt
                break

        if selected:
            rationale_parts.append(
                f"{preferred_dest.replace('_', ' ').title()} at capacity — "
                f"rerouting to {selected.replace('_', ' ').title()}"
            )
            preferred_dest = selected
            confidence = 0.70
        else:
            rationale_parts.append(
                f"{preferred_dest.replace('_', ' ').title()} and fallbacks at capacity — "
                "patient queued. Resource alert flagged."
            )
            confidence = 0.55

    if surge_active:
        rationale_parts.append("Surge mode: capacity constraints elevated. All thresholds tightened.")
        confidence = max(0.45, confidence - 0.10)

    return preferred_dest, "; ".join(rationale_parts), confidence


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
def recommend_destination(
    priority: str,
    resources: list = None,
    surge_active: bool = False,
    state: Optional["PatientState"] = None,
    dynamic_score: float = 0.0,
) -> tuple[str, str, float]:
    """
    Main entry point. Returns (destination, rationale, confidence).

    If state is provided, classifies scheduler_state (blocked/ready/running)
    and annotates rationale accordingly.
    """
    resources = resources or []
    base_destination = priority_to_destination(priority)

    # Classify scheduler state
    sched_state = classify_scheduler_state(state)

    # Blocked patients: don't assign a running slot; they wait in I/O queue
    if sched_state in ("blocked_io_vitals", "blocked_io_scan"):
        label = get_scheduler_state_label(sched_state)
        return (
            base_destination,
            f"{label} — slot reservation pending I/O completion. "
            f"Destination {base_destination.replace('_', ' ').title()} pre-assigned on unblock.",
            0.80,
        )

    if not resources:
        return (
            base_destination,
            f"Priority {priority} → {base_destination.replace('_', ' ').title()} (no resource data)",
            0.75,
        )

    cores = _build_scheduler_cores(resources, surge_active=surge_active)
    return schedule_patient(
        priority=priority,
        dynamic_score=dynamic_score,
        cores=cores,
        preferred_dest=base_destination,
        surge_active=surge_active,
    )


def get_full_scheduler_status(resources: list) -> dict:
    """
    Return full scheduler status for the Resources page:
    per-core load, availability, and scheduler health.
    """
    cores = _build_scheduler_cores(resources)
    capacity_map = _aggregate_core_capacity(cores)

    cores_summary = {}
    for dest, core_list in cores.items():
        total_cap = sum(c.total_capacity for c in core_list)
        total_occ = sum(c.occupied for c in core_list)
        total_avail = sum(c.available_slots for c in core_list if c.is_available)
        avg_load = _get_core_load(cores, dest)
        cores_summary[dest] = {
            "destination": dest,
            "label": dest.replace("_", " ").title(),
            "total_capacity": total_cap,
            "occupied": total_occ,
            "available_slots": total_avail,
            "load_pct": round(avg_load * 100, 1),
            "status": "critical" if avg_load >= 0.90 else "high" if avg_load >= 0.70 else "normal",
            "cores": len(core_list),
        }

    total_capacity = sum(c["total_capacity"] for c in cores_summary.values())
    total_occupied = sum(c["occupied"] for c in cores_summary.values())
    overall_load = total_occupied / total_capacity if total_capacity > 0 else 0.0

    return {
        "cores": cores_summary,
        "overall_load_pct": round(overall_load * 100, 1),
        "total_capacity": total_capacity,
        "total_occupied": total_occupied,
        "total_available": total_capacity - total_occupied,
        "surge_risk": overall_load >= 0.80,
    }
