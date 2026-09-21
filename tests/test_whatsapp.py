"""Tests for WhatsApp message delivery."""

import logging
from unittest.mock import Mock, patch

import pytest

from alfred.whatsapp import HarmlessWhatsAppLogFilter, send_whatsapp_message


def test_harmless_whatsapp_log_filter() -> None:
    """Hide retry-receipt noise without suppressing unrelated errors."""
    log_filter = HarmlessWhatsAppLogFilter()

    retry_record = logging.LogRecord(
        "whatsmeow.Client", logging.ERROR, "", 0, "Failed to handle retry receipt", (), None
    )
    error_record = logging.LogRecord("whatsmeow.Client", logging.ERROR, "", 0, "Delivery failed", (), None)

    assert not log_filter.filter(retry_record)
    assert log_filter.filter(error_record)


@patch("alfred.whatsapp.DISCONNECT_DELAY_SECONDS", 0)
@patch("alfred.whatsapp.DELIVERY_DELAY_SECONDS", 0)
@patch("alfred.whatsapp.NewClient")
def test_send_whatsapp_message(mock_client_class: Mock) -> None:
    """Send one message shortly after the client reports a connection."""
    client = mock_client_class.return_value
    callbacks: list[Mock] = []

    def register(_: object) -> object:
        def decorator(callback: Mock) -> Mock:
            callbacks.append(callback)
            return callback

        return decorator

    client.event.side_effect = register
    client.connect.side_effect = lambda: callbacks[0](client, Mock())

    send_whatsapp_message(recipient="+39 123 456 7890", message="Meteo")

    client.send_message.assert_called_once()
    assert client.send_message.call_args.kwargs["message"] == "Meteo"
    assert client.send_message.call_args.kwargs["to"].User == "391234567890"
    client.stop.assert_called_once_with()


@patch("alfred.whatsapp.DISCONNECT_DELAY_SECONDS", 0)
@patch("alfred.whatsapp.DELIVERY_DELAY_SECONDS", 0)
@patch("alfred.whatsapp.NewClient")
def test_send_whatsapp_message_propagates_delivery_error(mock_client_class: Mock) -> None:
    """Raise an error produced by Neonize after connecting."""
    client = mock_client_class.return_value
    callbacks: list[Mock] = []

    def register(_: object) -> object:
        def decorator(callback: Mock) -> Mock:
            callbacks.append(callback)
            return callback

        return decorator

    client.event.side_effect = register
    client.send_message.side_effect = RuntimeError("delivery failed")
    client.connect.side_effect = lambda: callbacks[0](client, Mock())

    with pytest.raises(RuntimeError, match="delivery failed"):
        send_whatsapp_message(recipient="391234567890", message="Meteo")

    client.stop.assert_called_once_with()
