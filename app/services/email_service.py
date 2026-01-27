from flask_mailman import EmailMessage
from flask import current_app


def send_email(pdf_path, recipients, subject, body_text, body_html=None):
    if not recipients:
        print("Weekly report: no active recipients")
        return False

    try:
        message = EmailMessage(
            subject=subject,
            body=body_text,
            html=body_html,
            to=[email for email in recipients],
        )

        message.attach_file(pdf_path)
        message.send()

        return True

    except Exception as e:
        print(f"Failed to send weekly report email: {e}")
        return False
