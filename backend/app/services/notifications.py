from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.models import AccessRequest, LoginHelpRequest


logger = logging.getLogger(__name__)


def access_request_notifications_configured() -> bool:
    return bool(
        settings.access_request_notification_email.strip()
        and settings.smtp_host.strip()
        and settings.smtp_from_email.strip()
    )


def send_access_request_notification(access_request: AccessRequest) -> bool:
    if not access_request_notifications_configured():
        logger.info(
            "Skipping access request email notification because SMTP configuration is incomplete."
        )
        return False

    message = EmailMessage()
    message["Subject"] = f"New LaborTrackIQ access request: {access_request.restaurant_name}"
    message["From"] = _format_sender()
    message["To"] = settings.access_request_notification_email.strip()
    message["Reply-To"] = access_request.email
    message.set_content(_build_access_request_email_body(access_request))

    smtp_client = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    with smtp_client(
        settings.smtp_host.strip(),
        settings.smtp_port,
        timeout=settings.smtp_timeout_seconds,
    ) as client:
        client.ehlo()
        if not settings.smtp_use_ssl and settings.smtp_use_tls:
            client.starttls()
            client.ehlo()
        if settings.smtp_username.strip() or settings.smtp_password:
            client.login(settings.smtp_username.strip(), settings.smtp_password)
        client.send_message(message)
    return True


def send_access_request_confirmation(access_request: AccessRequest) -> bool:
    if not access_request_notifications_configured():
        logger.info(
            "Skipping access request confirmation email because SMTP configuration is incomplete."
        )
        return False

    message = EmailMessage()
    message["Subject"] = "LaborTrackIQ request received"
    message["From"] = _format_sender()
    message["To"] = access_request.email
    if settings.support_reply_to_email.strip():
        message["Reply-To"] = settings.support_reply_to_email.strip()
    message.set_content(_build_access_request_confirmation_body(access_request))
    _send_email_message(message)
    return True


def send_login_help_request_notification(login_help_request: LoginHelpRequest) -> bool:
    if not access_request_notifications_configured():
        logger.info(
            "Skipping login help email notification because SMTP configuration is incomplete."
        )
        return False

    message = EmailMessage()
    message["Subject"] = f"LaborTrackIQ login help request: {login_help_request.email}"
    message["From"] = _format_sender()
    message["To"] = settings.access_request_notification_email.strip()
    message["Reply-To"] = login_help_request.email
    message.set_content(_build_login_help_request_email_body(login_help_request))

    smtp_client = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    with smtp_client(
        settings.smtp_host.strip(),
        settings.smtp_port,
        timeout=settings.smtp_timeout_seconds,
    ) as client:
        client.ehlo()
        if not settings.smtp_use_ssl and settings.smtp_use_tls:
            client.starttls()
            client.ehlo()
        if settings.smtp_username.strip() or settings.smtp_password:
            client.login(settings.smtp_username.strip(), settings.smtp_password)
        client.send_message(message)
    return True


def send_login_help_request_confirmation(login_help_request: LoginHelpRequest) -> bool:
    if not access_request_notifications_configured():
        logger.info(
            "Skipping login help confirmation email because SMTP configuration is incomplete."
        )
        return False

    message = EmailMessage()
    message["Subject"] = "LaborTrackIQ login help request received"
    message["From"] = _format_sender()
    message["To"] = login_help_request.email
    if settings.support_reply_to_email.strip():
        message["Reply-To"] = settings.support_reply_to_email.strip()
    message.set_content(_build_login_help_request_confirmation_body(login_help_request))
    _send_email_message(message)
    return True


def _format_sender() -> str:
    from_email = settings.smtp_from_email.strip()
    from_name = settings.smtp_from_name.strip()
    return f"{from_name} <{from_email}>" if from_name else from_email


def _send_email_message(message: EmailMessage) -> None:
    smtp_client = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    with smtp_client(
        settings.smtp_host.strip(),
        settings.smtp_port,
        timeout=settings.smtp_timeout_seconds,
    ) as client:
        client.ehlo()
        if not settings.smtp_use_ssl and settings.smtp_use_tls:
            client.starttls()
            client.ehlo()
        if settings.smtp_username.strip() or settings.smtp_password:
            client.login(settings.smtp_username.strip(), settings.smtp_password)
        client.send_message(message)


def _build_access_request_email_body(access_request: AccessRequest) -> str:
    locations = str(access_request.locations) if access_request.locations is not None else "Not provided"
    current_tools = access_request.current_tools or "Not provided"
    notes = access_request.notes or "Not provided"

    return (
        "A new restaurant requested access to LaborTrackIQ.\n\n"
        f"Restaurant / Group: {access_request.restaurant_name}\n"
        f"Best Contact: {access_request.contact_name}\n"
        f"Contact Email: {access_request.email}\n"
        f"Locations: {locations}\n"
        f"Current Tools: {current_tools}\n"
        f"Notes: {notes}\n"
        f"Source: {access_request.source}\n"
        f"Status: {access_request.status}\n"
        f"Submitted At: {access_request.created_at.isoformat() if access_request.created_at else 'Unknown'}\n"
    )


def _build_login_help_request_email_body(login_help_request: LoginHelpRequest) -> str:
    organization_reference = login_help_request.organization_reference or "Not provided"
    return (
        "A restaurant requested login help for LaborTrackIQ.\n\n"
        f"Organization Reference: {organization_reference}\n"
        f"Contact Email: {login_help_request.email}\n"
        f"Details: {login_help_request.details}\n"
        f"Source: {login_help_request.source}\n"
        f"Status: {login_help_request.status}\n"
        f"Submitted At: {login_help_request.created_at.isoformat() if login_help_request.created_at else 'Unknown'}\n"
    )


def _build_access_request_confirmation_body(access_request: AccessRequest) -> str:
    return (
        f"Hi {access_request.contact_name},\n\n"
        "We received your LaborTrackIQ access request.\n\n"
        "What happens next:\n"
        "- We review your restaurant details\n"
        "- We follow up about setup, access, and fit\n"
        "- We coordinate next steps with your team\n\n"
        f"Restaurant / Group: {access_request.restaurant_name}\n"
        f"Locations: {access_request.locations if access_request.locations is not None else 'Not provided'}\n\n"
        "If you need to add anything else, reply to this message or contact info@labortrackiq.com.\n\n"
        "LaborTrackIQ"
    )


def _build_login_help_request_confirmation_body(login_help_request: LoginHelpRequest) -> str:
    return (
        "We received your LaborTrackIQ login help request.\n\n"
        "Our team will follow up to help you regain access or confirm the next steps.\n\n"
        f"Organization Reference: {login_help_request.organization_reference or 'Not provided'}\n"
        f"Contact Email: {login_help_request.email}\n\n"
        "If you need to add anything else, reply to this message or contact info@labortrackiq.com.\n\n"
        "LaborTrackIQ"
    )
