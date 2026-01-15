from flask import Blueprint, jsonify, redirect, render_template, request, flash, url_for
from flask_login import login_required
from app.services.cpe_inventory import (
    get_cpe_records_view_data,
    get_cpe_records_history,
    update_cpe_records,
)


cpe_inventory_bp = Blueprint(
    "cpe_inventory",
    __name__,
    url_prefix="/cpe-records",
)


@cpe_inventory_bp.route("/")
@login_required
def cpe_records():
    data = get_cpe_records_view_data()

    return render_template("cpe_records.html", **data)


# UPDATE ROUTE FOR CPE-RECORDS TABLE, CALLED FROM INSIDE FORME INSIDE cpe-record
# THIS IS JSON API ROUTE, IT DOESNOT RETURN HTNL PAGE
@cpe_inventory_bp.route("/update", methods=["POST"])
@login_required
def cpe_records_update():
    data = request.get_json(silent=True)

    success, message = update_cpe_records(data or {})

    flash(message, "success" if success else "danger")

    # return {"status": "ok"}
    return jsonify(
        {
            "success": success,
            "message": message,
        }
    ), 200 if success else 403


@cpe_inventory_bp.route("/history/<int:id>")
@login_required
def cpe_records_city_history(id):
    page = request.args.get("page", 1, int)

    per_page = 20

    city, records, schema_list, error = get_cpe_records_history(id, page, per_page)

    if error:
        flash(error, "danger")
        return redirect(url_for("main.home"))

    return render_template(
        "cpe_records_history.html",
        records=records,
        schema=schema_list,
        city=city,
    )



@cpe_inventory_bp.route("/export/cpe-records.xlsx")
@login_required
def export_cpe_pivot_excel():
    pass
