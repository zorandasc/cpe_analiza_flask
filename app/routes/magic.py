from flask import (
    Blueprint,
    flash,
    redirect,
    session,
    url_for,
)
from flask_login import login_user

from app.models import UserRole
from app.services.magic import verify_login_token


magic_bp = Blueprint(
    "magic",
    __name__,
    url_prefix="/magic-login",
)


@magic_bp.route("/<token>")
def magic_login(token):
    user = verify_login_token(token)

    if not user or user.role != UserRole.VIEW:
        flash("Invalid or expired login link.")
        return redirect(url_for("auth.login"))

    login_user(user, remember=False)

    # the same as regular login users which session will expired in 60min
    session.permanent = True

    return redirect(url_for("charts.chart_home"))
