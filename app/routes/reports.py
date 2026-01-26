from flask import Blueprint, render_template
from flask_login import login_required
from app.services.reports import generate_pdf
from app.services.email_service import send_email
from flask import send_file

report_bp = Blueprint(
    "reports",
    __name__,
    url_prefix="/reports",
)


# GENERATE WEEKLY REPORT
# THIS ROUTE WILL BE HIT BY CRON JOB:
# 0 7 * * 1 curl http://localhost:5000/reports/weekly
@report_bp.route("/weekly")
@login_required
def generate_weekly_report():

    pdf_path = generate_pdf()

    # generate_excel()

    # Generate mail using for example flask-mailman
    #send_email(pdf_path)

    return send_file(
        pdf_path,
        as_attachment=True,
        download_name="weekly_report.pdf",
        mimetype='application/pdf'
    )

