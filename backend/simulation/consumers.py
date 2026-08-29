"""
WebSocket consumer for real-time ED updates.
Group: 'ed_live' — all connected clients receive broadcast events.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer


class EDLiveConsumer(AsyncWebsocketConsumer):
    GROUP_NAME = 'ed_live'

    async def connect(self):
        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()
        # Send connected acknowledgement
        await self.send(text_data=json.dumps({'type': 'connected', 'message': 'ED Live connected'}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def receive(self, text_data):
        """Handle messages from the client (e.g., ping)."""
        try:
            data = json.loads(text_data)
            if data.get('type') == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
        except (json.JSONDecodeError, KeyError):
            pass

    # Handler for group messages
    async def ed_event(self, event):
        """Relay group events to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': event.get('event_type'),
            'payload': event.get('payload'),
        }))
