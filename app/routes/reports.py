from flask import Blueprint
from flask_login import login_required
from app.services.reports import generate_pdf
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

    return send_file(
        pdf_path,
        as_attachment=True,
        download_name="weekly_report.pdf",
        mimetype="application/pdf",
    )
