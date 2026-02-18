from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.services.auth import login_to_app, logout_from_app


auth_bp = Blueprint(
    "auth",
    __name__,
)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        success, message = login_to_app(request.form)
        
        if success:
            flash(message, "success")
            return redirect(url_for("main.home"))
        
        # If it fails, we stay on the page and show the error
        flash(message, "danger")
        return render_template("login.html")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    success, message = logout_from_app()
    flash(message, "success" if success else "danger")
    return redirect(url_for("auth.login"))
