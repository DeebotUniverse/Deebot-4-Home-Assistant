"""Util module."""
from typing import List

from deebot_client.events.event_bus import EventListener


def unsubscribe_listeners(listeners: List[EventListener]) -> None:
    """Unsubscribe from all listeners."""
    for listener in listeners:
        listener.unsubscribe()
