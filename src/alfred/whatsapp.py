"""WhatsApp message delivery through Neonize."""

import logging
from threading import Timer
from time import sleep

from neonize.client import NewClient
from neonize.proto.Neonize_pb2 import Connected
from neonize.utils.jid import build_jid

DELIVERY_DELAY_SECONDS = 3.0
DISCONNECT_DELAY_SECONDS = 2.0


class HarmlessWhatsAppLogFilter(logging.Filter):
    """Hide known harmless WhatsApp client messages."""

    IGNORED_MESSAGES = (
        "Error sending close to websocket",
        "Failed to handle retry receipt",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        """Return false for known harmless client messages."""
        return not any(message in record.getMessage() for message in self.IGNORED_MESSAGES)


def send_whatsapp_message(recipient: str, message: str) -> None:
    """Connect to WhatsApp, send one message, and stop the client."""
    log_filter = HarmlessWhatsAppLogFilter()
    logging.getLogger("whatsmeow.Client").addFilter(log_filter)
    logging.getLogger("whatsmeow.Client.Socket").addFilter(log_filter)
    client = NewClient(name="sessione_whatsapp.db")
    delivery_error: Exception | None = None
    delivery_timer: Timer | None = None

    def deliver_message() -> None:
        nonlocal delivery_error
        try:
            phone_number = "".join(filter(str.isdigit, recipient))
            client.send_message(to=build_jid(phone_number=phone_number), message=message)
            sleep(DISCONNECT_DELAY_SECONDS)
        except Exception as error:
            delivery_error = error
        finally:
            client.stop()

    @client.event(Connected)
    def on_connected(_: NewClient, __: Connected) -> None:
        nonlocal delivery_timer
        delivery_timer = Timer(DELIVERY_DELAY_SECONDS, deliver_message)
        delivery_timer.name = "whatsapp-delivery"
        delivery_timer.start()

    client.connect()

    if delivery_timer is not None:
        delivery_timer.join()
    if delivery_error is not None:
        raise delivery_error
