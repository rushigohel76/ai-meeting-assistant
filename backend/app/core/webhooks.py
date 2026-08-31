import hmac


class WebhookSignatureError(Exception):
    pass


def verify_meetingbaas_webhook_secret(
    *,
    secret: str,
    headers: dict[str, str],
) -> None:
    received_secret = headers.get("x-mb-secret") or headers.get("x-meeting-baas-api-key")
    if not received_secret:
        raise WebhookSignatureError("Missing Meeting BaaS webhook secret header")

    if not hmac.compare_digest(received_secret, secret):
        raise WebhookSignatureError("Meeting BaaS webhook secret did not match")
