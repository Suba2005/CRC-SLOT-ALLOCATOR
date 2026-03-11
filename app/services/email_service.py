"""
Email service — encapsulates all SMTP logic and exposes a clean,
application‑independent API.  The Flask-Mail ``Mail`` instance lives
here so that callers do not need to import from the application package.

Public functions:

* ``init_mail(app)`` – initialise the mail extension.
* ``send_email`` – low level helper used by the others.
* ``send_test_email`` – used by the allocator blueprint to verify SMTP.
* ``send_login_email`` / ``send_logout_email`` – authentication hooks.
* ``send_allocation_summary`` – notify the user when a run completes.
* ``send_slot_allocation_email`` – per-student notification (unchanged).
* ``send_email_with_attachment`` – generic helper that can attach workbooks.
"""
from flask_mail import Mail, Message
from flask import current_app

mail = Mail()


def init_mail(app):
    """Initialise ``flask-mail`` with the given Flask app.

    This is typically called from ``create_app`` in ``app/__init__.py``.
    """
    mail.init_app(app)


# ── Generic send_email (reusable core) ──────────────────────────────────
def send_email(recipient: str, subject: str, body: str) -> bool:
    """
    Send a plain-text email to a single recipient.

    Parameters
    ----------
    recipient : str
        Recipient email address.
    subject : str
        Email subject line.
    body : str
        Plain-text email body.

    Returns
    -------
    bool
        True if sent successfully, False on error.
    """
    try:
        msg = Message(subject=subject, recipients=[recipient], body=body)
        mail.send(msg)
        current_app.logger.info(f"[Email] Sent '{subject}' to {recipient}")
        return True
    except Exception as e:
        current_app.logger.error(f"[Email Error] {e}")
        # Log SMTP config (never log actual credentials)
        current_app.logger.error(
            f"[Email Config] "
            f"MAIL_SERVER={current_app.config.get('MAIL_SERVER')}, "
            f"MAIL_PORT={current_app.config.get('MAIL_PORT')}, "
            f"MAIL_USE_TLS={current_app.config.get('MAIL_USE_TLS')}, "
            f"MAIL_USE_SSL={current_app.config.get('MAIL_USE_SSL')}, "
            f"MAIL_USERNAME={'(set)' if current_app.config.get('MAIL_USERNAME') else '(empty)'}, "
            f"MAIL_PASSWORD={'(set)' if current_app.config.get('MAIL_PASSWORD') else '(empty)'}, "
            f"MAIL_DEFAULT_SENDER={'(set)' if current_app.config.get('MAIL_DEFAULT_SENDER') else '(empty)'}"
        )
        return False


# ── Login notification ──────────────────────────────────────────────────

def send_login_email(username: str, email: str) -> bool:
    """
    Send a login alert message to the user.
    """
    subject = "CRC Portal Login Alert"
    body = (
        f"Hello {username},\n\n"
        f"You have successfully logged in to the CRC Portal.\n\n"
        f"If this was not you, please change your password immediately.\n\n"
        f"Regards\n"
        f"CRC Portal"
    )
    return send_email(email, subject, body)


# ── Logout notification ─────────────────────────────────────────────────

def send_logout_email(username: str, email: str) -> bool:
    """
    Notify the user that they have logged out.
    """
    subject = "CRC Portal Logout Notification"
    body = (
        f"Hello {username},\n\n"
        f"You have been successfully logged out of the CRC Portal.\n\n"
        f"Regards\n"
        f"CRC Portal"
    )
    return send_email(email, subject, body)


# ── Slot allocation result notification ──────────────────────────────────

def send_slot_allocation_email(
    student_name: str,
    email: str,
    day: str,
    period: str,
    panel: int = None,
) -> bool:
    """
    Send a GD/PI slot allocation notification to a student.

    Parameters
    ----------
    student_name : str
        Name of the student.
    email : str
        Student's email address.
    day : str
        Day of the allocated slot (e.g. "Monday").
    period : str
        Time period / slot string (e.g. "09:00 - 10:00").
    panel : int, optional
        Panel number if multiple panels are used.
    """
    subject = "GD/PI Slot Allocation"

    panel_line = f"\nPanel: {panel}" if panel else ""

    body = (
        f"Hello {student_name},\n\n"
        f"Your GD/PI slot has been allocated.\n\n"
        f"Day: {day}\n"
        f"Period: {period}"
        f"{panel_line}\n\n"
        f"Regards\n"
        f"CRC Portal"
    )
    return send_email(email, subject, body)


# ── Allocation report with Excel attachment ──────────────────────────────

def send_email_with_attachment(
    to: str | list[str],
    subject: str,
    body: str,
    attachment: bytes | None = None,
    attachment_filename: str = "allocation.xlsx",
) -> bool:
    """
    Send an email with optional Excel attachment.

    Parameters
    ----------
    to : str or list[str]
        Recipient email(s).
    subject : str
        Email subject line.
    body : str
        Email body (plain text).
    attachment : bytes, optional
        Raw file bytes to attach.
    attachment_filename : str
        Filename for the attachment.

    Returns
    -------
    bool
        True if sent successfully, False on error.
    """
    try:
        recipients = [to] if isinstance(to, str) else to
        msg = Message(subject=subject, recipients=recipients, body=body)

        if attachment:
            msg.attach(
                filename=attachment_filename,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                data=attachment,
            )

        mail.send(msg)
        current_app.logger.info(f"[Email] Sent '{subject}' to {recipients}")
        return True
    except Exception as e:
        current_app.logger.error(f"[Email Error] {e}")
        return False


# ── Convenience wrappers ─────────────────────────────────────────────────

def send_test_email(email: str, username: str) -> bool:
    """Send a simple test message to the given address."""
    subject = "CRC Portal — Test Email"
    body = (
        f"Hello {username},\n\n"
        f"This is a test email from the CRC Portal.\n"
        f"If you received it, your SMTP settings are correct.\n\n"
        f"Regards\n"
        f"CRC Portal"
    )
    return send_email(email, subject, body)


def send_allocation_summary(user_email: str, username: str, summary: dict) -> bool:
    """Notify the user who ran an allocation with a brief summary."""
    subject = "GD/PI Slot Allocation — Results Ready"
    body = (
        f"Hello {username},\n\n"
        f"Your GD/PI slot allocation has been completed.\n\n"
        f"Total students: {summary.get('total_roll', 0)}\n"
        f"Allocated: {summary.get('allocated_count', 0)}\n"
        f"Not available: {summary.get('not_available_count', 0)}\n"
        f"Overflow: {summary.get('overflow_count', 0)}\n\n"
        f"Log in to the CRC Portal to view full results and download the report.\n\n"
        f"Regards\n"
        f"CRC Portal"
    )
    return send_email(user_email, subject, body)
