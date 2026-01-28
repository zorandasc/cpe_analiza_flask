from flask import (
    current_app,
    Blueprint,
    send_file,
    flash,
    redirect,
    url_for,
    request,
    abort,
)
from flask_login import login_required
from app.utils.permissions import view_required
from app.services.reports import run_weekly_report_job, generate_pdf


report_bp = Blueprint(
    "reports",
    __name__,
    url_prefix="/reports",
)


# THIS ROUTE WILL BE HIT BY HOST CRON JOB, EVERY 10MIN:
# */10 * * * * curl -s -H "X-CRON-KEY: my-secret-key" http://localhost:5000/reports/weekly
@report_bp.route("/weekly", methods=["POST", "GET"])
def send_weekly_report():
    if request.headers.get("X-CRON-KEY") != current_app.config["CRON_SECRET"]:
        abort(403)
    result = run_weekly_report_job()
    return {"status": result}


# DOWNLOAD WEEKLY REPORT
@report_bp.route("/weekly/download")
@login_required
def download_weekly_report():
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
