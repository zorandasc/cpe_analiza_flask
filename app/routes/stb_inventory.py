from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.services.stb_inventory import (
    get_stb_records_view_data,
    update_recent_stb_inventory,
    update_iptv_users_count,
)

stb_inventory_bp = Blueprint(
    "stb_inventory",
    __name__,
    url_prefix="/stb-records",
)


@stb_inventory_bp.route("/")
@login_required
def stb_records():
    data = get_stb_records_view_data()
    return render_template("stb_records.html", **data)


@stb_inventory_bp.route("/update_stb", methods=["POST"])
@login_required
def update_stb_inventory():
    success, message = update_recent_stb_inventory(request.form)
    flash(message, "success" if success else "danger")
    return redirect(url_for("stb_inventory.stb_records"))

@stb_inventory_bp.route("/update_iptv_users", methods=["POST"])
@login_required
def update_iptv_users():
    success, message = update_iptv_users_count(request.form)
    flash(message, "success" if success else "danger")
    return redirect(url_for("stb_inventory.stb_records"))

