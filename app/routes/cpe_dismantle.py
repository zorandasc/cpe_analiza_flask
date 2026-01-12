from flask import Blueprint, jsonify, redirect, render_template, request, flash, url_for
from flask_login import login_required
from app.services.cpe_dismantle import (
    get_cpe_dismantle_view_data,
    update_cpe_dismantle,
    get_cpe_dismantle_history,
)


cpe_dismantle_bp = Blueprint(
    "cpe_dismantle_inventory",
    __name__,
    url_prefix="/cpe-dismantle-records",
)


@cpe_dismantle_bp.route("/")
@login_required
def cpe_dismantle_records():
    data = get_cpe_dismantle_view_data()

    return render_template("cpe_dismantle.html", **data)


@cpe_dismantle_bp.route("/update", methods=["POST"])
@login_required
def cpe_dismantle_update():
    data = request.get_json(silent=True)

    success, message = update_cpe_dismantle(data or {})

    flash(message, "success" if success else "danger")

    return jsonify(
        {
            "success": success,
            "message": message,
        }
    ), 200 if success else 403


@cpe_dismantle_bp.route("/history/<int:id>/<category>")
@login_required
def cpe_dismantle_city_history(id, category):
    page = request.args.get("page", 1, int)

    per_page = 20

    city, records, schema_list, category, error = get_cpe_dismantle_history(
        id, page, per_page, category
    )

    for r in records.items:
        print(r, "\n")

    if error:
        flash(error, "danger")
        return redirect(url_for("main.home"))

    return render_template(
        "cpe_dismantle_history.html",
        records=records,
        category=category,
        schema=schema_list,
        city=city,
    )
