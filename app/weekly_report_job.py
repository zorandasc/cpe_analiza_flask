from datetime import datetime
from app import create_app
from app.extensions import db
from app.models import ReportSetting, ReportRecipients
from app.services.reports import generate_pdf
from app.services.email_service import send_email

app = create_app()

# THIS PYTHON FILE IS CALLED BY CRON JOB
# EVERY DAY AT 12: # 0 12 * * * python /app/weekly_report_job.py
with app.app_context():
    settings = ReportSetting.query.first()

    # IS SENDING EMAIL ENABLED
    if not settings or not settings.enabled:
        print("Weekly report disabled")
        exit(0)

    # WHAT IS TODAY DATE
    today = datetime.today().weekday()

    # CRON JOB WILL HIT EVERY DAY AT 12:
    # BUT WE WILL SEND EMAIL ONLY AT DAY WE CHOOSE
    if today != settings.send_day:
        exit(0)

    # GET EMAILS OF RECIPIENTS
    recipients = [r.email for r in ReportRecipients.query.filter_by(active=True).all()]

    if not recipients:
        print("No recipients configured")
        exit(0)

    # GENERATE PDF REPORT
    pdf_path = generate_pdf()

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

    # SEND EMAIL TO RECIPIENTS
    send_email(
        pdf_path=pdf_path,
        recipients=recipients,
        subject=settings.emil_subject,
        body_text=body,
    )

    settings.last_sent_at = datetime.now()
    db.session.commit()
