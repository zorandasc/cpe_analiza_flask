from flask_mailman import EmailMessage
from flask import current_app


def send_email(pdf_path):
    subject = "Sedmični izvještaj o inventaru opreme"

    body = """
    Dragi Svi,

    U prilogu Vam dostavljamo sedmični izvještaj o inventaru CPE opreme.

    Sažetak:
    - Pregled stanja ukupne, raspoložive i demontirane CPE opreme
    - Značajne sedmične promjene
    - Analiza trendova

    S poštovanjem,
    Automatizovani sistem izvještavanja
    """

    message = EmailMessage(
        subject=subject,
        body=body,
        to=["zorand666@gmail.com"],
    )

    message.attach_file(pdf_path)

    message.send()
