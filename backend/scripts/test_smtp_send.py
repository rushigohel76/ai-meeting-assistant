#!/usr/bin/env python3
import asyncio
import os
import sys

sys.path.insert(0, "../")

from app.services.email import ResendEmailPayload, _send_smtp_email  # noqa: E402
from app.core.config import get_settings  # noqa: E402


async def main() -> None:
    settings = get_settings()

    to_email = os.environ.get("TEST_TO_EMAIL") or os.environ.get("TO_EMAIL")
    if not to_email:
        print("Set TEST_TO_EMAIL environment variable to the recipient address and try again.")
        raise SystemExit(1)

    payload = ResendEmailPayload(
        to_email=to_email,
        subject="MOM SMTP test",
        html="<p>This is a test message sent via SMTP from the MOM project.</p>",
        text="This is a test message sent via SMTP from the MOM project.",
    )

    await _send_smtp_email(
        payload=payload,
        from_email=settings.resend_from_email,
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=settings.smtp_password,
        use_tls=settings.smtp_use_tls,
    )
    print("SMTP send attempted (check recipient inbox or SMTP provider logs).")


if __name__ == "__main__":
    asyncio.run(main())
