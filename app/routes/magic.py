from datetime import timedelta

from flask import (
    Blueprint,
    current_app,
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


# This route will be hit by link embeded in email:
# login_link = f"{base_url}/magic-login/{token}"
@magic_bp.route("/<token>")
def magic_login(token):
    user = verify_login_token(token)

    if not user or user.role != UserRole.VIEW:
        flash("Invalid or expired login link.")
        return redirect(url_for("auth.login"))

    login_user(user, remember=False)

    # the same as regular login users
    # Override the default 1h session for this specific login
    session.permanent = True

    return redirect(url_for("charts.chart_home"))
