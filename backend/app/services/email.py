import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from html import escape

import httpx
from email.message import EmailMessage
import aiosmtplib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.meeting import Meeting
from app.models.summary import Summary
from app.models.user import User

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    pass


@dataclass(frozen=True)
class SummaryEmailContext:
    recipient_email: str
    recipient_name: str | None
    meeting_id: uuid.UUID
    meeting_title: str | None
    meeting_url: str
    created_at: datetime
    summary_text: str
    key_points: list[str]
    action_items: list[dict[str, str | None]]
    decisions: list[str]
    detail_url: str | None


@dataclass(frozen=True)
class ResendEmailPayload:
    to_email: str
    subject: str
    html: str
    text: str


async def send_password_reset_otp(to_email: str, otp: str) -> None:
    settings = get_settings()
    subject = "Your MOM password reset code"
    html = f"<p>Your password reset code is: <strong>{escape(otp)}</strong></p>"
    text = f"Your password reset code is: {otp}\n\nIf you did not request this, ignore this email."
    payload = ResendEmailPayload(to_email=to_email, subject=subject, html=html, text=text)

    await _send_resend_email(
        payload=payload,
        api_key=settings.resend_api_key,
        from_email=settings.resend_from_email,
        base_url=settings.resend_base_url,
    )


async def send_summary_email(
    meeting_id: uuid.UUID,
    recipient_email: str | None = None,
) -> None:
    settings = get_settings()

    async with AsyncSessionLocal() as db:
        context = await _load_summary_email_context(
            db=db,
            meeting_id=meeting_id,
            detail_url=_build_meeting_detail_url(meeting_id),
            recipient_email=recipient_email,
        )

    payload = build_summary_email_payload(context)
    await _send_resend_email(
        payload=payload,
        api_key=settings.resend_api_key,
        from_email=settings.resend_from_email,
        base_url=settings.resend_base_url,
    )


async def _load_summary_email_context(
    *,
    db: AsyncSession,
    meeting_id: uuid.UUID,
    detail_url: str | None,
    recipient_email: str | None = None,
) -> SummaryEmailContext:
    result = await db.execute(
        select(Meeting, Summary, User)
        .join(Summary, Summary.meeting_id == Meeting.id)
        .join(User, User.id == Meeting.user_id)
        .where(Meeting.id == meeting_id)
    )
    row = result.one_or_none()
    if row is None:
        raise EmailDeliveryError("Completed meeting summary was not found")

    meeting, summary, user = row
    email_address = recipient_email or user.email
    return SummaryEmailContext(
        recipient_email=email_address,
        recipient_name=user.full_name if email_address == user.email else None,
        meeting_id=meeting.id,
        meeting_title=meeting.title,
        meeting_url=meeting.meeting_url,
        created_at=meeting.created_at,
        summary_text=summary.summary_text,
        key_points=summary.key_points,
        action_items=summary.action_items,
        decisions=summary.decisions,
        detail_url=detail_url,
    )


def build_summary_email_payload(context: SummaryEmailContext) -> ResendEmailPayload:
    title = _meeting_title(context)
    subject = f"MOM summary: {title}"
    recipient_name = context.recipient_name.strip() if context.recipient_name else ""
    greeting = f"Hi {recipient_name}," if recipient_name else "Hi,"
    meeting_date = _format_meeting_date(context.created_at)

    key_points_html = _html_list(context.key_points, "No key points captured.")
    action_items_html = _html_list(
        [_format_action_item(action_item) for action_item in context.action_items],
        "No action items captured.",
    )
    decisions_html = _html_list(context.decisions, "No decisions captured.")
    detail_link_html = (
        f'<p><a href="{escape(context.detail_url, quote=True)}">Open the full meeting notes</a></p>'
        if context.detail_url
        else ""
    )

    html = f"""
<!doctype html>
<html>
  <body style="font-family: Arial, sans-serif; color: #111827; line-height: 1.5;">
    <p>{escape(greeting)}</p>
    <p>Your meeting summary is ready.</p>
    <h1 style="font-size: 22px; margin-bottom: 4px;">{escape(title)}</h1>
    <p style="color: #4b5563; margin-top: 0;">{escape(meeting_date)}</p>
    <h2 style="font-size: 16px;">Summary</h2>
    <p>{escape(context.summary_text)}</p>
    <h2 style="font-size: 16px;">Key points</h2>
    {key_points_html}
    <h2 style="font-size: 16px;">Action items</h2>
    {action_items_html}
    <h2 style="font-size: 16px;">Decisions</h2>
    {decisions_html}
    {detail_link_html}
  </body>
</html>
""".strip()

    text = "\n\n".join(
        section
        for section in [
            greeting,
            "Your meeting summary is ready.",
            f"Meeting: {title}",
            f"Date: {meeting_date}",
            f"Summary:\n{context.summary_text}",
            _text_list("Key points", context.key_points, "No key points captured."),
            _text_list(
                "Action items",
                [_format_action_item(action_item) for action_item in context.action_items],
                "No action items captured.",
            ),
            _text_list("Decisions", context.decisions, "No decisions captured."),
            f"Open the full meeting notes: {context.detail_url}" if context.detail_url else "",
        ]
        if section
    )

    return ResendEmailPayload(
        to_email=context.recipient_email,
        subject=subject,
        html=html,
        text=text,
    )


async def _send_resend_email(
    *,
    payload: ResendEmailPayload,
    api_key: str,
    from_email: str,
    base_url: str,
) -> None:
    settings = get_settings()

    # If SMTP is configured, use SMTP instead of Resend API
    if settings.smtp_host:
        await _send_smtp_email(
            payload=payload,
            from_email=from_email,
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_tls,
        )
        return
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/emails",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": from_email,
                    "to": [payload.to_email],
                    "subject": payload.subject,
                    "html": payload.html,
                    "text": payload.text,
                },
            )
    except httpx.TimeoutException as exc:
        logger.exception("Resend email request timed out")
        raise EmailDeliveryError("Resend email request timed out") from exc
    except httpx.TransportError as exc:
        logger.exception("Resend email request failed")
        raise EmailDeliveryError("Resend email request failed") from exc
    if response.status_code >= 400:
        # log response body to aid debugging (may include provider error details)
        try:
            resp_text = response.text
        except Exception:
            resp_text = "<unreadable response body>"
        logger.error(
            "Resend email request was rejected",
            extra={
                "status_code": response.status_code,
                "response_text": resp_text,
                "to": payload.to_email,
            },
        )
        short_resp = (resp_text[:1000] + "...") if len(resp_text) > 1000 else resp_text
        raise EmailDeliveryError(
            f"Resend email request was rejected: {response.status_code} - {short_resp}"
        )


async def _send_smtp_email(
    *,
    payload: ResendEmailPayload,
    from_email: str,
    host: str,
    port: int = 587,
    username: str | None = None,
    password: str | None = None,
    use_tls: bool = True,
) -> None:
    message = EmailMessage()
    message["From"] = from_email
    message["To"] = payload.to_email
    message["Subject"] = payload.subject
    message.set_content(payload.text)
    message.add_alternative(payload.html, subtype="html")

    try:
        await aiosmtplib.send(
            message,
            hostname=host,
            port=port,
            username=username,
            password=password,
            start_tls=use_tls,
            timeout=20.0,
        )
    except Exception as exc:
        logger.exception("SMTP email send failed")
        raise EmailDeliveryError("SMTP email send failed") from exc


def _build_meeting_detail_url(meeting_id: uuid.UUID) -> str | None:
    settings = get_settings()
    frontend_base_url = settings.frontend_base_url or next(
        (origin for origin in settings.cors_origins if origin and origin != "*"),
        None,
    )
    if not frontend_base_url:
        return None

    return f"{frontend_base_url.rstrip('/')}/meetings/{meeting_id}"


def _meeting_title(context: SummaryEmailContext) -> str:
    title = context.meeting_title.strip() if context.meeting_title else ""
    return title or "Meeting summary"


def _format_meeting_date(value: datetime) -> str:
    formatted = value.strftime("%b %d, %Y at %H:%M %Z").strip()
    return formatted.removesuffix(" at")


def _format_action_item(action_item: dict[str, str | None]) -> str:
    task = action_item.get("task") or "Untitled action item"
    owner = action_item.get("owner")
    if owner:
        return f"{task} - {owner}"
    return task


def _html_list(items: list[str], empty_text: str) -> str:
    cleaned_items = [item.strip() for item in items if item and item.strip()]
    if not cleaned_items:
        return f"<p>{escape(empty_text)}</p>"

    list_items = "".join(f"<li>{escape(item)}</li>" for item in cleaned_items)
    return f"<ul>{list_items}</ul>"


def _text_list(title: str, items: list[str], empty_text: str) -> str:
    cleaned_items = [item.strip() for item in items if item and item.strip()]
    if not cleaned_items:
        return f"{title}:\n{empty_text}"
    return f"{title}:\n" + "\n".join(f"- {item}" for item in cleaned_items)
