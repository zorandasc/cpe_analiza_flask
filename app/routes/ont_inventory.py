from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from app.services.ont_inventory import (
    get_ont_records_view_data,
    update_recent_ont_inventory,
)

ont_inventory_bp = Blueprint(
    "ont_inventory",
    __name__,
    url_prefix="/ont-records",
)


@ont_inventory_bp.route("/")
@login_required
def ont_records():
    data = get_ont_records_view_data()
    return render_template("ont_records.html", **data)


@ont_inventory_bp.route("/update_ont", methods=["POST"])
@login_required
def update_ont_inventory():
    success, message = update_recent_ont_inventory(request.form)
    flash(message, "success" if success else "danger")
    return redirect(url_for("ont_inventory.ont_records"))