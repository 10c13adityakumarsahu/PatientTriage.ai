"""
Broadcast helper — sends events to all connected WebSocket clients.
Uses Django Channels group_send via async_to_sync.
"""
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


GROUP_NAME = 'ed_live'


def broadcast_event(event_type: str, payload):
    """
    Broadcast a named event to all WebSocket clients in the ed_live group.
    Safe to call from synchronous Django views.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return  # No channel layer configured (tests)

    try:
        async_to_sync(channel_layer.group_send)(
            GROUP_NAME,
            {
                'type': 'ed_event',
                'event_type': event_type,
                'payload': payload,
            }
        )
    except Exception:
        # Never let broadcast failure break a request
        pass
