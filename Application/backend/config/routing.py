"""WebSocket URL routing for Django Channels."""
from django.urls import re_path
from simulation import consumers

websocket_urlpatterns = [
    re_path(r'ws/ed/live/$', consumers.EDLiveConsumer.as_asgi()),
]
