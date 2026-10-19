"""Loaded only by the offline test runner via PYTHONPATH."""
import socket


def blocked(*args, **kwargs):
    raise RuntimeError("Real network connections are disabled in tests")


socket.socket.connect = blocked
socket.socket.connect_ex = blocked
socket.create_connection = blocked
