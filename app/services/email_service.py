from flask_mailman import EmailMessage, EmailMultiAlternatives
from flask import current_app


def send_email(pdf_path, recipients, subject, body_text, body_html=""):
    if not recipients:
        print("Weekly report: no active recipients")
        return False

    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=body_text,
            to=[email for email in recipients],
        )

        # 2. Attach the HTML version as an alternative
        message.attach_alternative(body_html, "text/html")

        message.attach_file(pdf_path)
        message.send()

        return True

    except Exception as e:
        print(f"Failed to send weekly report email: {e}")
        return False
