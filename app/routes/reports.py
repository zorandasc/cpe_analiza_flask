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
def schedule_weekly_report():
    if request.headers.get("X-CRON-KEY") != current_app.config["CRON_JOB_SECRET"]:
        abort(403)
    # run_weekly_report_job() IS A SERVICE SCHEDULER
    result = run_weekly_report_job()
    return {"status": result}



