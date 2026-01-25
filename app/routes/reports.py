from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.services.reports import generate_pdf, send_email


report_bp = Blueprint(
    "reports",
    __name__,
    url_prefix="/reports",
)


# GENERATE WEEKLY REPORT
# THIS ROUTE WILL BE HIT BY CRON JOB:
# 0 7 * * 1 curl http://localhost:5000/reports/weekly
@report_bp.route("/weekly")
def generate_weekly_report():


    
    pdf_path = generate_pdf()

    # generate_excel()

    # Generate mail using for example flask-mailman
    # send_email(pdf_path)

    return "Weekly report generated", 200


@report_bp.route("/weekly/preview")
def preview_weekly_report():
    html = render_template("reports/weekly_report.html",  week="03 / 2026")
    return html
