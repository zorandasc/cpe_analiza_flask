from flask import Blueprint, send_file, flash, redirect, url_for
from flask_login import login_required
from app.services.reports import generate_pdf
from app.utils.permissions import view_required

report_bp = Blueprint(
    "reports",
    __name__,
    url_prefix="/reports",
)


# GENERATE WEEKLY REPORT
@report_bp.route("/weekly")
@login_required
def generate_weekly_report():
    if not view_required():
        flash("Niste Autorizovani.", "danger")
        return redirect(url_for("admin.dashboard"))
    pdf_path = generate_pdf()

    return send_file(
        pdf_path,
        as_attachment=True,
        download_name="weekly_report.pdf",
        mimetype="application/pdf",
    )
