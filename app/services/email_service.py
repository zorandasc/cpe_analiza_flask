from flask_mailman import EmailMessage, EmailMultiAlternatives
from flask import current_app
import os
from exchangelib import (
    Credentials,
    Account,
    Configuration,
    DELEGATE,
    Message,
    FileAttachment,
    HTMLBody,
)

# SEND EMAIL USING FLASK_MAILMAN: IT USE SMTP 587/25 PORT FOR SENDING MAIL
"""
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
      """


# SEND EMAIL USING exchangelib: it uses the same HTTPS "pipeline" as your browser and Outlook,
def send_email(pdf_path, recipients, subject, body_text, body_html=""):
    if not recipients:
        print("Weekly report: no active recipients")
        return False

    try:
        # 1. Setup Configuration (Keep these in your config or .env)
        credentials = Credentials(r"IN\cpe.reporting", os.environ.get("MAIL_PASSWORD"))

        # We specify the server directly to bypass DNS 'autodiscover' issues
        config = Configuration(server="webmail.mtel.ba", credentials=credentials)

        account = Account(
            primary_smtp_address="cpe.reporting@mtel.ba",
            config=config,
            autodiscover=False,
            access_type=DELEGATE,
        )

        # 2. Create the Message
        message = Message(
            account=account,
            subject=subject,
            # If body_html is provided, we use it; otherwise, we use body_text
            body=HTMLBody(body_html) if body_html else body_text,
            to_recipients=recipients,
        )

        # 3. Attach the PDF
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                file_content = f.read()
                message.attach(
                    FileAttachment(
                        name=os.path.basename(pdf_path), content=file_content
                    )
                )

            # 4. Send
        message.send_and_save()
        return True

    except Exception as e:
        print(f"Failed to send weekly report email via EWS: {e}")
        return False
