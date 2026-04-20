# from flask import current_app
import os
from exchangelib import (
    Credentials,
    Account,
    Configuration,
    DELEGATE,
    Message,
    FileAttachment,
    HTMLBody,
    Mailbox,
)

from app.models import ReportRecipients


# SEND EMAIL USING exchangelib: 
# it uses the same HTTPS "pipeline" as your browser and Outlook,
def send_email(pdf_path, body_html):
    recipients = [r.email for r in ReportRecipients.query.filter_by(active=True).all()]

    if not recipients:
        print("Weekly report: no active recipients")
        return False, "Nema primaoca."

    subject = "Sedmični izvještaj o CPE inventaru"

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

        # 3. Convert string emails to Mailbox objects for exchangelib
        to_recipients = [Mailbox(email_address=addr) for addr in recipients]

        # 2. Create the Message
        message = Message(
            account=account,
            subject=subject,
            body=HTMLBody(body_html),
            to_recipients=to_recipients,
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
        return True, "Email poslan uspiješno."

    except Exception as e:
        print(f"Failed to send weekly report email via EWS: {str(e)}")
        return False, "Dogodila se greška prilikom slanja email-a."
