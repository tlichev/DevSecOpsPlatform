from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/cli/<int:pk>/', consumers.SSHConsumer.as_asgi()),
]
