import logging

logger = logging.getLogger(__name__)


def send_alert(message: str) -> None:
    """
    Stub alert hook — swap for Slack/email/webhook in production.
    Logs at CRITICAL level so it's picked up by log shippers / paging tools.
    """
    logger.critical("ALERT: %s", message)
