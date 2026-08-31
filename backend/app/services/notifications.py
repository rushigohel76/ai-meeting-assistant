import logging
import uuid

from app.services.email import EmailDeliveryError, send_summary_email

logger = logging.getLogger(__name__)


async def enqueue_summary_email(meeting_id: uuid.UUID) -> None:
    try:
        await send_summary_email(meeting_id)
    except EmailDeliveryError:
        logger.exception("Summary email notification failed", extra={"meeting_id": str(meeting_id)})
        return
    except Exception:
        logger.exception(
            "Unexpected summary email notification failure",
            extra={"meeting_id": str(meeting_id)},
        )
        return

    logger.info("Summary email notification sent", extra={"meeting_id": str(meeting_id)})
