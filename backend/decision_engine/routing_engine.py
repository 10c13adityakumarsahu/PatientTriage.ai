"""
Routing Engine — recommends destination based on priority and resource capacity.
Returns a recommendation, not an autonomous command.
"""
from .priority_mapper import priority_to_destination

# Destination → queue type mapping
DESTINATION_TO_QUEUE = {
    "resuscitation": "resuscitation",
    "general_emergency": "general_emergency",
    "fast_track": "fast_track",
    "observation": "observation",
}


def recommend_destination(
    priority: str,
    resources: list = None,  # list of resource dicts with type, available_slots
    surge_active: bool = False,
) -> tuple[str, str, float]:
    """
    Returns (destination, rationale, confidence).
    """
    base_destination = priority_to_destination(priority)
    resources = resources or []

    # Build capacity map
    capacity_map = {}
    for r in resources:
        rtype = r.get("resource_type", "")
        slots = r.get("available_slots", 0)
        capacity_map[rtype] = capacity_map.get(rtype, 0) + slots

    rationale_parts = []
    confidence = 0.90

    # Check if preferred destination has capacity
    preferred_resource = _destination_to_resource(base_destination)
    available = capacity_map.get(preferred_resource, None)

    if available is None:
        # No resource data — still recommend based on priority
        rationale_parts.append(f"Priority {priority} → {base_destination}")
        confidence = 0.75
    elif available == 0:
        # Preferred is full — try alternatives
        alt = _find_alternative(base_destination, priority, capacity_map, surge_active)
        if alt and alt != base_destination:
            rationale_parts.append(
                f"{base_destination.replace('_', ' ').title()} at capacity — rerouting to {alt.replace('_', ' ').title()}"
            )
            base_destination = alt
            confidence = 0.70
        else:
            rationale_parts.append(f"{base_destination.replace('_', ' ').title()} at capacity — flagging pressure")
            confidence = 0.60
    else:
        rationale_parts.append(
            f"Priority {priority} → {base_destination.replace('_', ' ')} ({available} slots available)"
        )

    if surge_active:
        rationale_parts.append("Surge mode active — capacity constraints elevated")
        confidence = max(0.50, confidence - 0.10)

    return base_destination, "; ".join(rationale_parts), confidence


def _destination_to_resource(destination: str) -> str:
    mapping = {
        "resuscitation": "resus_bay",
        "general_emergency": "treatment_room",
        "fast_track": "fast_track_room",
        "observation": "observation_bed",
    }
    return mapping.get(destination, "treatment_room")


def _find_alternative(preferred: str, priority: str, capacity_map: dict, surge: bool) -> str:
    """Find next-best destination when preferred is full."""
    # Fallback chains by priority
    fallbacks = {
        "resuscitation": ["general_emergency"],
        "general_emergency": ["observation", "fast_track"],
        "fast_track": ["observation", "general_emergency"],
        "observation": ["general_emergency"],
    }
    for alt in fallbacks.get(preferred, []):
        resource = _destination_to_resource(alt)
        if capacity_map.get(resource, 0) > 0:
            return alt
    return preferred  # no better option
