from datetime import datetime
from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import login_required, current_user
from sqlalchemy.dialects.postgresql import insert
from werkzeug.security import generate_password_hash
from sqlalchemy.orm import selectinload
from app.extensions import db
from app.services.email_service import send_email
from app.services.magic import generate_link_for_view_user
from app.services.reports import generate_pdf
from app.utils.permissions import view_required, admin_required
from app.services.admin import update_cpe_type
from app.services.access_inventory import (
    parce_excel_segments,
    save_imported_segments_to_db,
)

from app.models import (
    Cities,
    CityTypeEnum,
    CpeInventory,
    CpeDismantle,
    CpeBroken,
    CpeTypeEnum,
    CpeTypes,
    DismantleTypes,
    AccessInventory,
    AccessTypes,
    StbInventory,
    StbTypes,
    IptvUsers,
    UserActivity,
    UserRole,
    Users,
    ReportSetting,
    ReportRecipients,
    CityVisibilitySettings,
    user_cities,
)


admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
)


@admin_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("admin.html")


###########################################################
# ---------------ROUTES FOR MAIN CPE TABLES-------------------------
############################################################
@admin_bp.route("/cpe_inventory")
@login_required
def cpe_inventory():
    if not admin_required():
        flash("Niste Autorizovani.", "danger")
        return redirect(url_for("admin.dashboard"))

    # THIS REQUEST ARG WE ARE GETTING FROM TEMPLATE <a LINK:
    # href="{{ url_for('admin_cpe_records', page=pagination.next_num, sort=sort_by, direction=direction) }}"
    page = request.args.get("page", 1, type=int)
    per_page = 50

    # WHEN INCICIALY LANDING ON PAGE
    # DEFAULT VIEW JE SORT BY UPDATE_AT AND DESC, THE MOST RESCENT ON THE TOP
    sort_by = request.args.get("sort", "updated_at")
    direction = request.args.get("direction", "desc")

    # filters
    week_end = request.args.get("week_end", type=str)
    city_id = request.args.get("city_id", type=int)

    # Whitelist allowed sort columns (prevents SQL injection)
    allowed_sorts = [
        "id",
        "city_id",
        "cpe_type_id",
        "week_end",
        "updated_at",
        "created_at",
    ]
    if sort_by not in allowed_sorts:
        sort_by = "id"

    query = CpeInventory.query

    # 🔍 FILTERS
    if week_end:
        query = query.filter(CpeInventory.week_end == week_end)

    if city_id:
        query = query.filter(CpeInventory.city_id == city_id)

    order_column = getattr(CpeInventory, sort_by)

    if direction == "desc":
        order_column = order_column.desc()

    pagination = query.order_by(order_column).paginate(
        page=page, per_page=per_page, error_out=False
    )

    cities = Cities.query.order_by(Cities.id).all()
    cpe_types = (
        CpeTypes.query.filter_by(visible_in_total=True).order_by(CpeTypes.id).all()
    )

    return render_template(
        "admin/cpe_inventory.html",
        records=pagination.items,
        pagination=pagination,
        # pass argument because of refresh, it must be preserved
        sort_by=sort_by,
        direction=direction,
        cities=cities,
        cpe_types=cpe_types,
        week_end=week_end,
        city_id=city_id,
    )


@admin_bp.route("/cpe_inventory/upsert", methods=["POST"])
@login_required
def upsert_cpe_inventory():
    if not admin_required():
        return redirect(url_for("admin.cpe_inventory"))

    city_id = request.form.get("city_id")

    city = Cities.query.get(city_id)
    if not city:
        flash("Greška: Skladište ne postoji.", "danger")
        return redirect(url_for("admin.cpe_inventory"))

    week_end = request.form.get("week_end")

    # 1. Validate Friday in Python
    try:
        date_obj = datetime.strptime(week_end, "%Y-%m-%d")
        if date_obj.weekday() != 4:  # Python: Monday=0, Friday=4
            flash("Greška: Datum mora biti petak!", "danger")
            return redirect(url_for("admin.cpe_inventory"))
    except ValueError:
        flash("Neispravan format datuma.", "danger")
        return redirect(url_for("admin.cpe_inventory"))

    cpe_types = (
        CpeTypes.query.filter_by(visible_in_total=True).order_by(CpeTypes.id).all()
    )

    for cpe in cpe_types:
        # Get the quantity for this specific type from the form
        qty = request.form.get(f"cpe_{cpe.id}", 0, type=int)

        # SQLALCHEMY Upsert Logic
        stmt = insert(CpeInventory).values(
            city_id=city_id, week_end=week_end, cpe_type_id=cpe.id, quantity=qty
        )

        upsert_stmt = stmt.on_conflict_do_update(
            constraint="uq_city_cpe_week",
            set_={"quantity": qty, "updated_at": db.func.now()},
        )

        db.session.execute(upsert_stmt)

    db.session.commit()

    formatted_date = date_obj.strftime("%d.%m.%Y")
    flash(
        f"Uspješno ažurirano stanje za: **{city.name}** (Sedmica: {formatted_date})",
        "success",
    )
    return redirect(url_for("admin.cpe_inventory"))


# ------------------------------------------------------------


@admin_bp.route("/cpe_dismantle")
@login_required
def cpe_dismantle():
    if not admin_required():
        flash("Niste Autorizovani.", "danger")
        return redirect(url_for("admin.dashboard"))

    # THIS REQUEST ARG WE ARE GETTING FROM TEMPLATE <a LINK:
    # href="{{ url_for('admin_cpe_records', page=pagination.next_num, sort=sort_by, direction=direction) }}"
    page = request.args.get("page", 1, type=int)
    per_page = 50

    # WHEN INCICIALY LANDING ON PAGE
    # DEFAULT VIEW JE SORT BY UPDATE_AT AND DESC, THE MOST RESCENT ON THE TOP
    sort_by = request.args.get("sort", "updated_at")
    direction = request.args.get("direction", "desc")

    # filters
    week_end = request.args.get("week_end", type=str)
    city_id = request.args.get("city_id", type=int)

    # Whitelist allowed sort columns (prevents SQL injection)
    allowed_sorts = [
        "id",
        "city_id",
        "cpe_type_id",
        "week_end",
        "updated_at",
        "created_at",
    ]

    if sort_by not in allowed_sorts:
        sort_by = "id"

    query = CpeDismantle.query

    # 🔍 FILTERS
    if week_end:
        query = query.filter(CpeDismantle.week_end == week_end)

    if city_id:
        query = query.filter(CpeDismantle.city_id == city_id)

    order_column = getattr(CpeDismantle, sort_by)
    if direction == "desc":
        order_column = order_column.desc()

    pagination = query.order_by(order_column).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # THIS IS DATA FOR SELECTION IN CITY FILTER
    cities = (
        Cities.query.filter(Cities.type == CityTypeEnum.IJ.value)
        .order_by(Cities.id)
        .all()
    )

    return render_template(
        "admin/cpe_dismantle.html",
        records=pagination.items,
        pagination=pagination,
        sort_by=sort_by,
        direction=direction,
        cities=cities,
        week_end=week_end,
        city_id=city_id,
    )


@admin_bp.route("/cpe_dismantle_inventory/update/<int:id>", methods=["POST"])
@login_required
def update_cpe_dismantle_inventory(id):
    if not admin_required():
        return redirect(url_for("admin.cpe_dismantle"))

    table_row = CpeDismantle.query.get_or_404(id)

    quantity = request.form.get("quantity", type=int)

    if quantity is None:
        flash("Neispravna količina.", "danger")
        return redirect(url_for("admin.cpe_dismantle"))

    table_row.quantity = quantity
    table_row.updated_at = datetime.now()

    try:
        db.session.commit()
        flash("Stanje CPE demontaža uspješno izmijenjeno!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Greška prilikom izmjene: {e}", "danger")
        return redirect(url_for("admin.cpe_dismantle"))

    return redirect(
        url_for(
            "admin.cpe_dismantle",
            week_end=request.args.get("week_end"),
            city_id=request.args.get("city_id"),
        )
    )


# -------------------------------------------------------------
@admin_bp.route("/cpe_broken")
@login_required
def cpe_broken():
    if not admin_required():
        flash("Niste Autorizovani.", "danger")
        return redirect(url_for("admin.dashboard"))

    # THIS REQUEST ARG WE ARE GETTING FROM TEMPLATE <a LINK:
    # href="{{ url_for('admin_cpe_records', page=pagination.next_num, sort=sort_by, direction=direction) }}"
    page = request.args.get("page", 1, type=int)
    per_page = 50

    # WHEN INCICIALY LANDING ON PAGE
    # DEFAULT VIEW JE SORT BY UPDATE_AT AND DESC, THE MOST RESCENT ON THE TOP
    sort_by = request.args.get("sort", "updated_at")
    direction = request.args.get("direction", "desc")

    # filters
    week_end = request.args.get("week_end", type=str)
    city_id = request.args.get("city_id", type=int)

    # Whitelist allowed sort columns (prevents SQL injection)
    allowed_sorts = [
        "id",
        "city_id",
        "cpe_type_id",
        "week_end",
        "updated_at",
        "created_at",
    ]
    if sort_by not in allowed_sorts:
        sort_by = "id"

    query = CpeBroken.query

    # 🔍 FILTERS
    if week_end:
        query = query.filter(CpeBroken.week_end == week_end)

    if city_id:
        query = query.filter(CpeBroken.city_id == city_id)

    order_column = getattr(CpeBroken, sort_by)
    if direction == "desc":
        order_column = order_column.desc()

    pagination = query.order_by(order_column).paginate(
        page=page, per_page=per_page, error_out=False
    )

    cities = Cities.query.order_by(Cities.id).order_by(Cities.id).all()

    cpe_types = (
        CpeTypes.query.filter_by(visible_in_broken=True).order_by(CpeTypes.id).all()
    )

    return render_template(
        "admin/cpe_broken.html",
        records=pagination.items,
        pagination=pagination,
        # pass argument because of refresh, it must be preserved
        sort_by=sort_by,
        direction=direction,
        cities=cities,
        cpe_types=cpe_types,
        week_end=week_end,
        city_id=city_id,
    )


@admin_bp.route("/cpe_broken/upsert", methods=["POST"])
@login_required
def upsert_cpe_broken():
    if not admin_required():
        return redirect(url_for("admin.cpe_broken"))

    city_id = request.form.get("city_id")

    city = Cities.query.get(city_id)
    if not city:
        flash("Greška: Skladište ne postoji.", "danger")
        return redirect(url_for("admin.cpe_broken"))

    week_end = request.form.get("week_end")

    # 1. Validate Friday in Python
    try:
        date_obj = datetime.strptime(week_end, "%Y-%m-%d")
        if date_obj.weekday() != 4:  # Python: Monday=0, Friday=4
            flash("Greška: Datum mora biti petak!", "danger")
            return redirect(url_for("admin.cpe_broken"))
    except ValueError:
        flash("Neispravan format datuma.", "danger")
        return redirect(url_for("admin.cpe_broken"))

    cpe_types = (
        CpeTypes.query.filter_by(visible_in_broken=True).order_by(CpeTypes.id).all()
    )

    for cpe in cpe_types:
        # Get the quantity for this specific type from the form
        qty = request.form.get(f"cpe_{cpe.id}", 0, type=int)

        # SQLALCHEMY Upsert Logic
        stmt = insert(CpeBroken).values(
            city_id=city_id, week_end=week_end, cpe_type_id=cpe.id, quantity=qty
        )

        upsert_stmt = stmt.on_conflict_do_update(
            constraint="uqb_city_cpe_week",
            set_={"quantity": qty, "updated_at": db.func.now()},
        )

        db.session.execute(upsert_stmt)

    db.session.commit()

    formatted_date = date_obj.strftime("%d.%m.%Y")
    flash(
        f"Uspješno ažurirano stanje za: **{city.name}** (Sedmica: {formatted_date})",
        "success",
    )
    return redirect(url_for("admin.cpe_broken"))


# COMMON FOR ALL 3 CPE TABLES
@admin_bp.route("/get_cpe_values/<table_type>")
@login_required
def get_cpe_values_for_city_week(table_type):
    city_id = request.args.get("city_id", type=int)
    week_end = request.args.get("week_end", type=str)

    model_map = {"inventory": CpeInventory, "broken": CpeBroken}

    TargetModel = model_map.get(table_type)

    if not TargetModel:
        return jsonify({"error": "Invalid table type"}), 400

    # Fetch existing records for this combo
    records = TargetModel.query.filter_by(city_id=city_id, week_end=week_end).all()

    if not records:
        return jsonify({"exists": False})

    # Create a dictionary of {cpe_type_id: quantity}
    values_dict = {r.cpe_type_id: r.quantity for r in records}

    return jsonify(
        {
            "exists": True,
            "values": values_dict,
        }
    )


###########################################################
# ---------------ROUTES FOR MAIN STB TABLES-------------------------
############################################################


@admin_bp.route("/stb_inventory")
@login_required
def stb_inventory():
    if not admin_required():
        flash("Niste Autorizovani.", "danger")
        return redirect(url_for("admin.dashboard"))

    # THIS REQUEST ARG WE ARE GETTING FROM TEMPLATE <a LINK:
    # href="{{ url_for('admin_cpe_records', page=pagination.next_num, sort=sort_by, direction=direction) }}"
    page = request.args.get("page", 1, type=int)
    per_page = 50

    # WHEN INCICIALY LANDING ON PAGE
    # DEFAULT VIEW JE SORT BY UPDATE_AT AND DESC, THE MOST RESCENT ON THE TOP
    sort_by = request.args.get("sort", "updated_at")
    direction = request.args.get("direction", "desc")

    # filters
    week_end = request.args.get("week_end", type=str)
    stb_type_id = request.args.get("stb_type_id", type=int)

    # Whitelist allowed sort columns (prevents SQL injection)
    allowed_sorts = ["id", "stb_type_id", "week_end", "updated_at", "created_at"]
    if sort_by not in allowed_sorts:
        sort_by = "id"

    query = StbInventory.query

    # 🔍 FILTERS
    if week_end:
        query = query.filter(StbInventory.week_end == week_end)

    if stb_type_id:
        query = query.filter(StbInventory.stb_type_id == stb_type_id)

    order_column = getattr(StbInventory, sort_by)
    if direction == "desc":
        order_column = order_column.desc()

    pagination = query.order_by(order_column).paginate(
        page=page, per_page=per_page, error_out=False
    )

    stbs = StbTypes.query.order_by(StbTypes.id).all()

    return render_template(
        "admin/stb_inventory.html",
        records=pagination.items,
        pagination=pagination,
        sort_by=sort_by,
        direction=direction,
        stbs=stbs,
        week_end=week_end,
        stb_type_id=stb_type_id,
    )


@admin_bp.route("/stb_inventory/update/<int:id>", methods=["POST"])
@login_required
def update_stb_inventory(id):
    if not admin_required():
        return redirect(url_for("admin.stb_inventory"))

    table_row = StbInventory.query.get_or_404(id)

    quantity = request.form.get("quantity", type=int)

    if quantity is None:
        flash("Neispravna količina.", "danger")
        return redirect(url_for("admin.stb_inventory"))

    table_row.quantity = quantity
    table_row.updated_at = datetime.now()

    try:
        db.session.commit()
        flash("STB stanje uspješno izmijenjeno!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Greška prilikom izmjene: {e}", "danger")
        return redirect(url_for("admin.stb_inventory"))

    return redirect(
        url_for(
            "admin.stb_inventory",
            week_end=request.args.get("week_end"),
            stb_type_id=request.args.get("stb_type_id"),
        )
    )


# --------------------------------------------------------------


@admin_bp.route("/iptv_users_inventory")
@login_required
def iptv_users_inventory():
    if not admin_required():
        flash("Niste Autorizovani.", "danger")
        return redirect(url_for("admin.dashboard"))

    # THIS REQUEST ARG WE ARE GETTING FROM TEMPLATE <a LINK:
    # href="{{ url_for('admin_cpe_records', page=pagination.next_num, sort=sort_by, direction=direction) }}"
    page = request.args.get("page", 1, type=int)
    per_page = 50

    # WHEN INCICIALY LANDING ON PAGE
    # DEFAULT VIEW JE SORT BY UPDATE_AT AND DESC, THE MOST RESCENT ON THE TOP
    sort_by = request.args.get("sort", "updated_at")
    direction = request.args.get("direction", "desc")

    # filters
    week_end = request.args.get("week_end", type=str)

    # Whitelist allowed sort columns (prevents SQL injection)
    allowed_sorts = ["id", "week_end", "updated_at", "created_at"]
    if sort_by not in allowed_sorts:
        sort_by = "id"

    query = IptvUsers.query

    # 🔍 FILTERS
    if week_end:
        query = query.filter(IptvUsers.week_end == week_end)

    order_column = getattr(IptvUsers, sort_by)
    if direction == "desc":
        order_column = order_column.desc()

    pagination = query.order_by(order_column).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template(
        "admin/iptv_users_inventory.html",
        records=pagination.items,
        pagination=pagination,
        sort_by=sort_by,
        direction=direction,
        week_end=week_end,
    )


@admin_bp.route("/iptv_users_inventory/update/<int:id>", methods=["POST"])
@login_required
def update_iptv_users_inventory(id):
    if not admin_required():
        return redirect(url_for("admin.iptv_users_inventory"))

    table_row = IptvUsers.query.get_or_404(id)

    total_users = request.form.get("total_users", type=int)

    if total_users is None:
        flash("Neispravna količina.", "danger")
        return redirect(url_for("admin.iptv_users_inventory"))

    table_row.total_users = total_users
    table_row.updated_at = datetime.now()

    try:
        db.session.commit()
        flash("Stanje broja IPTV korisnika uspješno izmijenjeno!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Greška prilikom izmjene: {e}", "danger")
        return redirect(url_for("admin.iptv_users_inventory"))

    return redirect(
        url_for("admin.iptv_users_inventory", week_end=request.args.get("week_end"))
    )


# ------------------------------------------------------------------------


@admin_bp.route("/access_inventory")
@login_required
def access_inventory():
    if not admin_required():
        flash("Niste Autorizovani.", "danger")
        return redirect(url_for("admin.dashboard"))

    # THIS REQUEST ARG WE ARE GETTING FROM TEMPLATE <a LINK:
    # href="{{ url_for('admin_cpe_records', page=pagination.next_num, sort=sort_by, direction=direction) }}"
    page = request.args.get("page", 1, type=int)
    per_page = 50

    # WHEN INCICIALY LANDING ON PAGE
    # DEFAULT VIEW JE SORT BY UPDATE_AT AND DESC, THE MOST RESCENT ON THE TOP
    sort_by = request.args.get("sort", "updated_at")
    direction = request.args.get("direction", "desc")

    # filters
    month_end = request.args.get("month_end", type=str)
    access_type_id = request.args.get("access_type_id", type=int)
    city_id = request.args.get("city_id", type=int)

    # Whitelist allowed sort columns (prevents SQL injection)
    allowed_sorts = ["id", "city_id", "month_end", "updated_at", "created_at"]
    if sort_by not in allowed_sorts:
        sort_by = "id"

    query = AccessInventory.query

    # 🔍 FILTERS
    if month_end:
        query = query.filter(AccessInventory.month_end == month_end)

    if access_type_id:
        query = query.filter(AccessInventory.access_type_id == access_type_id)

    if city_id:
        query = query.filter(AccessInventory.city_id == city_id)

    order_column = getattr(AccessInventory, sort_by)
    if direction == "desc":
        order_column = order_column.desc()

    pagination = query.order_by(order_column).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # THIS IS DATA FOR SELECTION IN ACCESS FILTER
    access = AccessTypes.query.order_by(AccessTypes.id).all()

    # THIS IS DATA FOR SELECTION IN CITY FILTER
    cities = (
        Cities.query.filter(Cities.type == CityTypeEnum.IJ.value)
        .order_by(Cities.id)
        .all()
    )

    return render_template(
        "admin/access_inventory.html",
        records=pagination.items,
        pagination=pagination,
        sort_by=sort_by,
        direction=direction,
        access=access,
        cities=cities,
        month_end=month_end,
        access_type_id=access_type_id,
        city_id=city_id,
    )


@admin_bp.route("/access_inventory/update/<int:id>", methods=["POST"])
@login_required
def update_access_inventory(id):
    if not admin_required():
        return redirect(url_for("admin.access_inventory"))

    table_row = AccessInventory.query.get_or_404(id)

    quantity = request.form.get("quantity", type=int)

    if quantity is None:
        flash("Neispravna količina.", "danger")
        return redirect(url_for("admin.access_inventory"))

    table_row.quantity = quantity
    table_row.updated_at = datetime.now()

    try:
        db.session.commit()
        flash("ONT stanje uspješno izmijenjeno!", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Greška prilikom izmjene: {e}", "danger")
        return redirect(url_for("admin.access_inventory"))

    return redirect(
        url_for(
            "admin.access_inventory",
            month_end=request.args.get("month_end"),
            access_type_id=request.args.get("access_type_id"),
            city_id=request.args.get("city_id"),
        )
    )


# called from js inside access_records.html
@admin_bp.route("/access_inventory/upload-excel", methods=["POST"])
@login_required
def import_access_records_excel():
    if "file" not in request.files:
        return "No file part", 400

    file = request.files["file"]

    # The dictionary returned here contains 'segments', 'match', etc.
    results = parce_excel_segments(file)

    # RETRUN PARSED SEGMENTS TO MODAL FOR DISPLAY
    return results  # Flask converts dict to JSON automatically


@admin_bp.route("/access_inventory/save-segments", methods=["POST"])
@login_required
def save_access_imported_segments():
    data = request.get_json()

    segments = data.get("segments", {})
    selected_date = data.get("selected_date")

    if not segments:
        return jsonify(
            {
                "success": False,
                "message": "error: Nema podataka",
            }
        ), 400

    success, message = save_imported_segments_to_db(segments, selected_date)

    flash(message, "success" if success else "danger")

    return jsonify(
        {
            "success": success,
            "message": message,
        }
    ), 200 if success else 403


###########################################################
# ---------------ROUTES FOR CITIES CRUD--------------------------
############################################################
@admin_bp.route("/cities")
@login_required
def cities():
    if not admin_required():
        flash("Niste Autorizovani.", "danger")
        return redirect(url_for("admin.dashboard"))

    major_cities = (
        Cities.query.filter(Cities.parent_city_id.is_(None)).order_by(Cities.name).all()
    )
    return render_template("admin/cities.html", major_cities=major_cities)


@admin_bp.route("/cities/add", methods=["GET", "POST"])
@login_required
def add_city():
    if not admin_required():
        return redirect(url_for("admin.cities"))

    # THIS IS FOR SUMBITING REQUEST
    if request.method == "POST":
        name = request.form.get("name")
        parent_city_id = request.form.get("parent_city_id", type=int)
        type_string = request.form.get("type")

        # 1. Validation: Convert string to Enum object safely
        try:
            selected_type = CityTypeEnum(type_string)
        except ValueError:
            flash("Izabrani tip nije važeći.", "danger")
            return redirect(url_for("admin.add_city"))

        # Validation: name must be unique
        existing_city = Cities.query.filter_by(name=name).first()
        if existing_city:
            flash("Skladište već postoji", "danger")
            return redirect(url_for("admin.add_city"))

        if parent_city_id:
            parent = Cities.query.get(parent_city_id)
            if not parent:
                flash("Grad ne postoji.", "danger")
                return redirect(url_for("admin.add_city"))

        db.session.add(
            Cities(name=name, parent_city_id=parent_city_id, type=selected_type)
        )
        db.session.commit()
        flash("Novo skladište dodano", "success")
        return redirect(url_for("admin.cities"))

    cities = (
        Cities.query.filter(Cities.parent_city_id.is_(None)).order_by(Cities.name).all()
    )

    types = [t.value for t in CityTypeEnum]
    # THIS IS FOR GET REQUEST WHEN OPENING ADD FORM
    return render_template("admin/cities_add.html", types=types, cities=cities)


@admin_bp.route("/cities/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_city(id):
    if not admin_required():
        return redirect(url_for("admin.cities"))

    city = Cities.query.get_or_404(id)

    if request.method == "POST":
        name = request.form.get("name")
        type_string = request.form.get("type")
        parent_city_id = request.form.get("parent_city_id", type=int)

        # 1. Validation: Convert string to Enum object safely
        try:
            selected_type = CityTypeEnum(type_string)
        except ValueError:
            flash("Izabrani tip nije važeći.", "danger")
            return redirect(url_for("admin.edit_city", id=id))

        # name uniqueness (except current name)
        existing_city = Cities.query.filter(
            Cities.name == name, Cities.id != id
        ).first()
        if existing_city:
            flash("Skladiste već postoji!", "danger")
            return redirect(url_for("admin.edit_city", id=id))

        if parent_city_id:
            parent = Cities.query.get(parent_city_id)
            if not parent:
                flash("Grad ne postoji.", "danger")
                return redirect(url_for("admin.add_city"))

        city.name = name
        city.type = selected_type
        city.parent_city_id = parent_city_id

        try:
            db.session.commit()
            flash("Skladiste uspješno izmijenjeno!", "success")
            return redirect(url_for("admin.cities", id=id))
        except Exception as e:
            db.session.rollback()
            flash(f"Greška prilikom izmjene: {e}", "danger")
            return redirect(url_for("admin.edit_city", id=id))

    cities = (
        Cities.query.filter(Cities.parent_city_id.is_(None)).order_by(Cities.name).all()
    )

    types = [t.value for t in CityTypeEnum]

    return render_template(
        "admin/cities_edit.html", city=city, types=types, cities=cities
    )


@admin_bp.route("/cities/delete/<int:id>")
@login_required
def delete_city(id):
    if not admin_required():
        return redirect(url_for("admin.cities"))

    city = Cities.query.get_or_404(id)

    city_cpe_count = (
        db.session.query(CpeInventory.id).filter_by(city_id=city.id).first()
    )
    city_dismantle_count = (
        db.session.query(CpeDismantle.id).filter_by(city_id=city.id).first()
    )
    city_broken_count = (
        db.session.query(CpeBroken.id).filter_by(city_id=city.id).first()
    )
    city_access_count = (
        db.session.query(AccessInventory.id).filter_by(city_id=city.id).first()
    )
    city_users_count = db.session.query(user_cities).filter_by(city_id=city.id).first()
    subcities_count = (
        db.session.query(Cities.id).filter_by(parent_city_id=city.id).first()
    )

    errors = []

    # PROTECT CITY DELETE: block if related rows exist
    if city_cpe_count:
        errors.append("Skladište ima aktivne unose u inventaru ukupne CPE opreme.")
    if city_dismantle_count:
        errors.append("Skladište ima aktivne unose u inventaru demontirane CPE opreme.")
    if city_broken_count:
        errors.append("Skladište ima aktivne unose u inventaru neispravne CPE opreme.")
    if city_access_count:
        errors.append("Skladište ima aktivne unose u inventaru pristupne tehnologije.")
    if city_users_count:
        errors.append("Skladište ima aktivne unose u korisnicima.")
    if subcities_count:
        errors.append("Skladište ima podgradove.")

    if errors:
        flash(f"Skladište nemože biti obrisano jer: {', '.join(errors)}.", "danger")
        return redirect(url_for("admin.cities"))

    flash("Skladište obrisano!", "success")
    db.session.delete(city)
    db.session.commit()
    return redirect(url_for("admin.cities"))


###########################################################
# ---------------ROUTES FOR CITIES VISIBILITY--------------------------
############################################################
@admin_bp.route("/cities/cities_visibility")
@login_required
def cities_visibility():
    if not admin_required():
        flash("Niste Autorizovani.", "danger")
        return redirect(url_for("admin.dashboard"))

    cities = Cities.query.order_by(Cities.id).all()
    settings = CityVisibilitySettings.query.all()

    datasets = {
        "cpe_inventory": "CPE Oprema",
        "cpe_dismantle": "CPE Demontirana",
        "cpe_broken": "CPE Neispravna",
        "access_inventory": "Pristupna FTTH mreža",
    }

    # Map for quick lookup
    settings_map = {(s.city_id, s.dataset_key): s for s in settings}

    # In template we use settings_map to find setting object
    # from city_visibility_settings table using city_id and dataset_key
    # for city in cities:
    #    for key in datasets.keys():
    #        setting=settings_map.get((city.id, key))
    #        print(setting)

    return render_template(
        "admin/cities_visibility.html",
        cities=cities,
        datasets=datasets,
        settings_map=settings_map,
    )


@admin_bp.route("/cities/cities_visibility/update", methods=["POST"])
@login_required
def cities_visibility_update():
    if not admin_required():
        return redirect(url_for("admin.dashboard"))

    # 1. Get the values from form submision
    city_id = int(request.form["city_id"])
    dataset_key = request.form["dataset_key"]
    field = request.form["field"]
    value = request.form.get("value") == "true"

    # 2. find the the row in city_visibility_settings table
    setting = CityVisibilitySettings.query.filter_by(
        city_id=city_id, dataset_key=dataset_key
    ).first()

    # 3. Change boolean fields for city_id/dataset_key in db
    if not setting:
        setting = CityVisibilitySettings(city_id=city_id, dataset_key=dataset_key)
        db.session.add(setting)

    setattr(setting, field, value)

    db.session.commit()

    return redirect(request.referrer)


###########################################################
# ---------------ROUTES FOR USERS CRUD--------------------------
############################################################
@admin_bp.route("/users")
@login_required
def users():
    if not admin_required():
        flash("Niste Autorizovani.", "danger")
        return redirect(url_for("admin.dashboard"))

    # WHY selectinload?
    # BECAUSE USERS AND CITIES ARE N0W MANY-TO-MANY RELATION
    # IF WE DO THIS users = Users.query.order_by(Users.id).all()
    # WE ARE GENERATING N+1 PROBLEM
    users = Users.query.options(selectinload(Users.cities)).order_by(Users.id).all()

    return render_template("admin/users.html", users=users)


@admin_bp.route("/users/add", methods=["GET", "POST"])
@login_required  # AUTHENTICATE
def add_user():
    if not admin_required():  # AUTHORIZE
        return redirect(url_for("admin.users"))

    # THIS IS FOR SUMBITING A NEW REQUEST
    if request.method == "POST":
        username = request.form.get("username")
        plain_password = request.form.get("password")
        # CHOOSED FROM SELECTION IN ADD FORM
        city_ids = request.form.getlist("city_ids", type=int)
        # CHOOSED FROM SELECTION IN ADD FORM
        role_string = request.form.get("role")

        # 1. Validation: Convert string to Enum object safely
        try:
            selected_role = UserRole(role_string)
        except ValueError:
            flash("Izabrana rola nije važeća.", "danger")
            return redirect(url_for("admin.add_user"))

        # Validation: username must be unique
        existing_user = Users.query.filter_by(username=username).first()
        if existing_user:
            flash("Korisnićko ime već postoji.", "danger")
            return redirect(url_for("admin.add_user"))

        if selected_role == UserRole.USER_CPE and not city_ids:
            flash("Korisnik sa rolom 'user_cpe' mora imati izabran grad.", "danger")
            return redirect(url_for("admin.add_user"))

        cities_selected = Cities.query.filter(Cities.id.in_(city_ids)).all()

        password_hash = generate_password_hash(plain_password)

        user = Users(
            username=username,
            password_hash=password_hash,
            role=selected_role,  # SQLAlchemy handles the conversion to DB string
            cities=cities_selected,
        )
        try:
            db.session.add(user)
            db.session.commit()
            flash("User created successfully", "success")
            return redirect(url_for("admin.users"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating user: {e}", "danger")
            return redirect(url_for("admin.add_user"))

    # GET Request
    cities = Cities.query.order_by(Cities.name).all()

    roles = [r.value for r in UserRole]

    # THIS IS FOR GET REQUEST WHEN OPENING BLANK ADD FORM
    return render_template("admin/users_add.html", cities=cities, roles=roles)


@admin_bp.route("/users/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_user(id):
    if not admin_required():
        return redirect(url_for("admin.users"))

    user = Users.query.options(selectinload(Users.cities)).get_or_404(id)

    if request.method == "POST":
        username = request.form.get("username")
        plain_password1 = request.form.get("password1")
        plain_password2 = request.form.get("password2")
        # CHOOSED FROM SELECTION IN ADD FORM
        city_ids = request.form.getlist("city_ids", type=int)
        # CHOOSED FROM SELECTION IN ADD FORM
        role_string = request.form.get("role")

        try:
            selected_role = UserRole(role_string)
        except ValueError:
            flash("Izabrana rola nije važeća.", "danger")
            return redirect(url_for("admin.edit_user", id=id))

        # Username uniqueness (except current user)
        existing_user = Users.query.filter(
            Users.username == username, Users.id != id
        ).first()

        if existing_user:
            flash("Username već postoji!", "danger")
            return redirect(url_for("admin.edit_user", id=id))

        if plain_password1 or plain_password2:
            if plain_password1 != plain_password2:
                flash("Šifre nisu iste!", "danger")
                return redirect(url_for("admin.edit_user", id=id))
            # Update password hash only if a new password is entered
            user.password_hash = generate_password_hash(plain_password1)

        # Prevent Admin from Demoting Themselves
        if (
            current_user.id == user.id
            and user.role == UserRole.ADMIN
            and selected_role != UserRole.ADMIN
        ):
            flash("Ne možete ukloniti svoju admin ulogu!", "danger")
            return redirect(url_for("admin.edit_user", id=id))

        # if role changed to user
        if selected_role == UserRole.USER_CPE and not city_ids:
            flash("Korisnik sa rolom 'user_cpe' mora imati izabran grad.", "danger")
            return redirect(url_for("admin.add_user"))

        cities_selected = Cities.query.filter(Cities.id.in_(city_ids)).all()

        user.username = username
        user.cities = cities_selected
        user.role = selected_role
        user.updated_at = datetime.now()

        try:
            db.session.commit()
            flash("Korisnik uspješno izmijenjen!", "success")
            return redirect(url_for("admin.users"))
        except Exception as e:
            db.session.rollback()
            flash(f"Greška prilikom izmjene korisnika: {e}", "danger")
            return redirect(url_for("admin.edit_user", id=id))

    # GET Request
    cities = Cities.query.order_by(Cities.name).all()
    # Correct way to get all values from Enum for the dropdown
    roles = [r.value for r in UserRole]

    return render_template(
        "admin/users_edit.html", user=user, roles=roles, cities=cities
    )


@admin_bp.route("/users/delete/<int:id>")
@login_required
def delete_user(id):
    if not admin_required():
        return redirect(url_for("admin.users"))

    user = Users.query.get_or_404(id)

    if user.role == UserRole.ADMIN:
        admin_count = Users.query.filter_by(role=UserRole.ADMIN).count()
        if admin_count < 2:
            flash("Ne možete obrisati posljednjeg admina!", "danger")
            return redirect(url_for("admin.users"))

    db.session.delete(user)
    db.session.commit()
    flash("Korisnik obrisan", "success")
    return redirect(url_for("admin.users"))


###########################################################
# ---------------ROUTES FOR CPE TYPES CRUD--------------------------
############################################################
@admin_bp.route("/cpe_types")
@login_required
def cpe_types():
    if not admin_required():
        flash("Niste Autorizovani.", "danger")
        return redirect(url_for("admin.dashboard"))
    cpes = CpeTypes.query.order_by(CpeTypes.id).all()
    return render_template("admin/cpe_types.html", cpes=cpes)


@admin_bp.route("/cpe_types/add", methods=["GET", "POST"])
@login_required
def add_cpe_type():
    if not admin_required():
        return redirect(url_for("admin.cpe_types"))

    # THIS IS FOR SUMBITING REQUEST
    if request.method == "POST":
        name = request.form.get("name")
        label = request.form.get("label")
        type = request.form.get("type")

        # Validation: name must be unique
        existing_cpe_type = CpeTypes.query.filter_by(name=name).first()
        if existing_cpe_type:
            flash("Tip CPE već postoji", "danger")
            return redirect(url_for("admin.add_cpe_type"))

        db.session.add(CpeTypes(name=name, label=label, type=type))
        db.session.commit()
        return redirect(url_for("admin.cpe_types"))

    # PROBLEM WITH THIS IT IS ONLY GIVE ME TYPES OF ALREADY
    # EXISISTING RECORDS, IF IT DOESNOT EXISISTIN TABLE IT WONT LIST
    # types = db.session.query(CpeTypes.type).distinct().all()
    # types = [t[0] for t in types]  # flatten list of tuples
    types = [member.value for member in CpeTypeEnum]

    # THIS IS FOR GET REQUEST WHEN INICIALY OPENING ADD FORM
    return render_template("admin/cpe_types_add.html", types=types)


@admin_bp.route("/cpe_types/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_cpe_type(id):
    if not admin_required():
        return redirect(url_for("admin.cpe_types"))

    cpe = CpeTypes.query.get_or_404(id)

    types = [member.value for member in CpeTypeEnum]

    if request.method == "POST":
        form_data = {
            "name": request.form.get("name"),
            "label": request.form.get("label"),
            "type": request.form.get("type"),
            "order_total": request.form.get("order_in_total"),
            "order_dismantle": request.form.get("order_in_dismantle"),
            "order_broken": request.form.get("order_in_broken"),
            "header_color": request.form.get("header_color"),
            "has_remote": "has_remote" in request.form,
            "has_adapter": "has_adapter" in request.form,
            "visible_in_total": "visible_in_total" in request.form,
            "visible_in_dismantle": "visible_in_dismantle" in request.form,
            "visible_in_broken": "visible_in_broken" in request.form,
        }

        success, message = update_cpe_type(id, form_data)

        flash(message, "success" if success else "danger")

        if success:
            return redirect(url_for("admin.cpe_types"))
        return redirect(url_for("admin.edit_cpe_type", id=id))

    return render_template(
        "admin/cpe_types_edit.html",
        cpe=cpe,
        types=types,
    )


@admin_bp.route("/cpe_types/delete/<int:id>")
@login_required
def delete_cpe_type(id):
    if not admin_required():
        return redirect(url_for("admin.cpe_types"))

    cpe = CpeTypes.query.get_or_404(id)

    cpe_total_count = (
        db.session.query(CpeInventory.id).filter_by(cpe_type_id=cpe.id).first()
    )
    cpe_dismantle_count = (
        db.session.query(CpeDismantle.id).filter_by(cpe_type_id=cpe.id).first()
    )
    cpe_broken_count = (
        db.session.query(CpeBroken.id).filter_by(cpe_type_id=cpe.id).first()
    )

    errors = []

    # PROTECT CPE DELETE: block if related rows exist
    if cpe_total_count:
        errors.append("CPE ima aktivne unose u inventaru ukupne CPE opreme.")
    if cpe_dismantle_count:
        errors.append("CPE ima aktivne unose u inventaru demontirane CPE opreme.")
    if cpe_broken_count:
        errors.append("CPE ima aktivne unose u inventaru neispravne CPE opreme.")

    if errors:
        flash(f"CPE nemože biti obrisan jer: {', '.join(errors)}.", "danger")
        return redirect(url_for("admin.cpe_types"))

    flash("CPE uređaj obrisan!", "success")
    db.session.delete(cpe)
    db.session.commit()
    return redirect(url_for("admin.cpe_types"))


###########################################################
# ---------------ROUTES FOR STB TYPES CRUD--------------------------
############################################################
@admin_bp.route("/stb_types")
@login_required
def stb_types():
    if not admin_required():
        flash("Niste Autorizovani.", "danger")
        return redirect(url_for("admin.dashboard"))
    stbs = StbTypes.query.order_by(StbTypes.id).all()
    return render_template("admin/stb_types.html", stbs=stbs)


@admin_bp.route("/stb_types/add", methods=["GET", "POST"])
@login_required
def add_stb_type():
    if not admin_required():
        return redirect(url_for("admin.stb_types"))

    # THIS IS FOR SUMBITING REQUEST
    if request.method == "POST":
        name = request.form.get("name")
        label = request.form.get("label")

        # Validation: name must be unique
        existing_stb_type = StbTypes.query.filter_by(name=name).first()
        if existing_stb_type:
            flash("Tip STB već postoji", "danger")
            return redirect(url_for("admin.add_stb_type"))

        db.session.add(StbTypes(name=name, label=label))
        db.session.commit()
        return redirect(url_for("admin.stb_types"))

    # THIS IS FOR GET REQUEST WHEN INICIALY OPENING ADD FORM
    return render_template(
        "admin/stb_types_add.html",
    )


@admin_bp.route("/stb_types/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_stb_type(id):
    if not admin_required():
        return redirect(url_for("admin.stb_types"))

    stb = StbTypes.query.get_or_404(id)

    if request.method == "POST":
        name = request.form.get("name")
        label = request.form.get("label")

        # Username uniqueness (except current user)
        existing_stb_type = StbTypes.query.filter(
            StbTypes.name == name, StbTypes.id != id
        ).first()
        if existing_stb_type:
            flash("Tip STB opreme već postoji!", "danger")
            return redirect(url_for("admin.edit_stb_type", id=id))

        stb.id = id
        stb.name = name
        stb.label = label
        stb.is_active = "is_active" in request.form  # THIS IS THE CORRECT WAY

        try:
            db.session.commit()
            flash("Stb tip uspješno izmijenjen!", "success")
            return redirect(url_for("admin.stb_types"))
        except Exception as e:
            db.session.rollback()
            flash(f"Greška prilikom izmjene stb tipa: {e}", "danger")
            return redirect(url_for("admin.edit_stb_type", id=id))

    return render_template("admin/stb_types_edit.html", stb=stb)


@admin_bp.route("/stb_types/delete/<int:id>")
@login_required
def delete_stb_type(id):
    if not admin_required():
        return redirect(url_for("admin.stb_types"))

    stb = StbTypes.query.get_or_404(id)

    stb_in_inventory = (
        db.session.query(StbInventory.id).filter_by(stb_type_id=stb.id).first()
    )

    # PROTECT stb DELETE: block if related rows exist
    if stb_in_inventory:
        flash(
            "STB nemože biti obrisan, ima aktivne unose u inventaru STB opreme. Možete ga onemogućit.",
            "danger",
        )
        return redirect(url_for("admin.stb_types"))

    flash("Stb uređaj obrisan!", "success")
    db.session.delete(stb)
    db.session.commit()
    return redirect(url_for("admin.stb_types"))


###########################################################
# ---------------ROUTES FOR DISMANTLE TYPES CRUD-------------------------
############################################################
@admin_bp.route("/dismantle_status")
@login_required
def dismantle_status():
    if not admin_required():
        flash("Niste Autorizovani.", "danger")
        return redirect(url_for("admin.dashboard"))
    status = DismantleTypes.query.order_by(DismantleTypes.id).all()
    return render_template("admin/dismantle_types.html", status=status)


@admin_bp.route("/dismantle_status/add", methods=["GET", "POST"])
@login_required
def add_dismantle_status():
    if not admin_required():
        return redirect(url_for("admin.dismantle_status"))

    # THIS IS FOR GET REQUEST WHEN INICIALY OPENING ADD FORM
    return render_template(
        "admin/dismantle_types_add.html",
    )


@admin_bp.route("/dismantle_status/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_dismantle_status(id):
    if not admin_required():
        return redirect(url_for("admin.dismantle_status"))

    dismantle = DismantleTypes.query.get_or_404(id)

    if request.method == "POST":
        label = request.form.get("label")

        dismantle.id = id
        dismantle.label = label

        try:
            db.session.commit()
            flash("Tip demontaže uspješno izmijenjen!", "success")
            return redirect(url_for("admin.dismantle_status"))
        except Exception as e:
            db.session.rollback()
            flash(f"Greška prilikom izmjene tipa demontaže: {e}", "danger")
            return redirect(url_for("admin.edit_dismantle_status", id=id))

    return render_template("admin/dismantle_types_edit.html", dismantle=dismantle)


###########################################################
# ---------------ROUTES FOR ACCESS TYPES CRUD--------------------------
############################################################
@admin_bp.route("/access_types")
@login_required
def access_types():
    if not admin_required():
        flash("Niste Autorizovani.", "danger")
        return redirect(url_for("admin.dashboard"))

    all_access = AccessTypes.query.order_by(AccessTypes.id).all()

    return render_template("admin/access_types.html", all_access=all_access)


@admin_bp.route("/access_types/add", methods=["GET", "POST"])
@login_required
def add_access_types():
    if not admin_required():
        return redirect(url_for("admin.access_types"))

    # THIS IS FOR SUMBITING REQUEST
    if request.method == "POST":
        name = request.form.get("name")
        label = request.form.get("label")

        # Validation: name must be unique
        existing_access_type = AccessTypes.query.filter_by(name=name).first()
        if existing_access_type:
            flash("Pistupna već postoji", "danger")
            return redirect(url_for("admin.add_access_types"))

        db.session.add(AccessTypes(name=name, label=label))
        db.session.commit()
        return redirect(url_for("admin.access_types"))

    # THIS IS FOR GET REQUEST WHEN INICIALY OPENING ADD FORM
    return render_template(
        "admin/access_types_add.html",
    )


@admin_bp.route("/access_types/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_access_types(id):
    if not admin_required():
        return redirect(url_for("admin.access_types"))

    access = AccessTypes.query.get_or_404(id)

    if request.method == "POST":
        name = request.form.get("name")
        label = request.form.get("label")

        # Username uniqueness (except current user)
        existing_access_type = AccessTypes.query.filter(
            AccessTypes.name == name, AccessTypes.id != id
        ).first()
        if existing_access_type:
            flash("Tip pristupna već postoji!", "danger")
            return redirect(url_for("admin.edit_access_types", id=id))

        access.id = id
        access.name = name
        access.label = label
        access.is_active = "is_active" in request.form  # THIS IS THE CORRECT WAY

        try:
            db.session.commit()
            flash("Pristupna uspješno izmijenjena!", "success")
            return redirect(url_for("admin.access_types"))
        except Exception as e:
            db.session.rollback()
            flash(f"Greška prilikom izmjene pristupne tehnologije: {e}", "danger")
            return redirect(url_for("admin.edit_access_types", id=id))

    return render_template("admin/access_types_edit.html", access=access)


@admin_bp.route("/access_types/delete/<int:id>")
@login_required
def delete_access_types(id):
    if not admin_required():
        return redirect(url_for("admin.access_types"))

    access = AccessTypes.query.get_or_404(id)

    access_count = (
        db.session.query(AccessInventory.id).filter_by(access_type_id=access.id).first()
    )

    # PROTECT CITY DELETE: block if related rows exist
    if access_count:
        flash(
            "Nemože biti brisano! Pristupna tehnologija ima aktivne unose. Možete ju onemogućiti.",
            "danger",
        )
        return redirect(url_for("admin.access_types"))

    flash("Pristupna tehnologija obrisana!", "success")
    db.session.delete(access)
    db.session.commit()
    return redirect(url_for("admin.access_types"))


###########################################################
# ---------------ROUTES FOR REPORT PAGE SETTTINGS-------------------------
############################################################


@admin_bp.route("/reports/settings", methods=["GET", "POST"])
@login_required  # AUTENTIFICATION
def report_settings():
    if not view_required():  # AUTHORIZATION
        return redirect(url_for("admin.report_settings"))
    # ReportSettin should only have one row
    settings = ReportSetting.query.first()

    if request.method == "POST":
        settings.enabled = "enabled" in request.form
        settings.send_day = int(request.form["send_day"])
        settings.send_time = datetime.strptime(
            request.form["send_time"], "%H:%M"
        ).time()
        db.session.commit()

        flash("Podešavanja sačuvana.", "success")

    # Dsiplay recipients to jinja template
    recipients = ReportRecipients.query.order_by(ReportRecipients.email).all()

    return render_template(
        "admin/report_settings.html", settings=settings, recipients=recipients
    )


@admin_bp.route("/reports/recipients/add", methods=["POST"])
@login_required
def report_add_recipient():
    if not admin_required():
        return redirect(url_for("admin.report_settings"))

    email = request.form["email"].lower().strip()

    db.session.add(ReportRecipients(email=email))
    db.session.commit()

    return redirect(url_for("admin.report_settings"))


@admin_bp.route("/reports/recipients/remove/<int:id>")
@login_required
def report_remove_recipient(id):
    if not admin_required():
        return redirect(url_for("admin.report_settings"))

    email = ReportRecipients.query.get_or_404(id)

    flash("Email obrisan!", "success")
    db.session.delete(email)
    db.session.commit()
    return redirect(url_for("admin.report_settings"))


# DOWNLOAD WEEKLY pdf REPORT MANNUALY
@admin_bp.route("/reports/download")
@login_required
def download_weekly_report():
    if not view_required():
        flash("Niste Autorizovani.", "danger")
        return redirect(url_for("admin.report_settings"))
    pdf_path = generate_pdf()

    return send_file(
        pdf_path,
        as_attachment=True,
        download_name="weekly_report.pdf",
        mimetype="application/pdf",
    )


# GENERATE EMAIL MANNUALY
@admin_bp.route("/reports/send_weekly", methods=["POST"])
def send_weekly_report():
    if not admin_required():  # AUTHORIZATION
        return redirect(url_for("admin.report_settings"))

    pdf_path = generate_pdf()

    try:
        magic_link = generate_link_for_view_user()
    except RuntimeError as e:
        flash(str(e), "danger")
        return redirect(url_for("admin.dashboard"))

    # SEND EMAIL TO RECIPIENTS, RETUNRS: BOOLEAN and STRING REASON
    success, message = send_email(pdf_path=pdf_path, link=magic_link)

    flash(f"Status: {message}", "success" if success else "danger")

    return redirect(url_for("admin.report_settings"))


###########################################################
# ---------------ROUTES FOR USER ACTIVITY--------------------------
############################################################


@admin_bp.route("/activity")
@login_required
def activity_logs():
    query = UserActivity.query.join(Users)

    # Filters
    user_id = request.args.get("user_id")
    action = request.args.get("action")
    table_name = request.args.get("table_name")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    page = request.args.get("page", 1, type=int)

    if user_id:
        query = query.filter(UserActivity.user_id == int(user_id))

    if action:
        query = query.filter(UserActivity.action == action)

    if table_name:
        query = query.filter(UserActivity.table_name == table_name)

    if date_from:
        date_from = datetime.strptime(date_from, "%Y-%m-%d")
        query = query.filter(UserActivity.timestamp >= date_from)

    if date_to:
        date_to = datetime.strptime(date_to, "%Y-%m-%d")
        query = query.filter(UserActivity.timestamp <= date_to)

    logs = query.order_by(UserActivity.timestamp.desc()).paginate(
        page=page, per_page=50, error_out=False
    )

    users = Users.query.order_by(Users.username).all()

    # ovo je za paginacione linkove u template
    # da ne bi srukali svaki argument u svaki paginacioni link
    # izbacujemo page jer njega unutar template saljemo odvojeno u odnosu na bunch
    args = request.args.to_dict()
    args.pop("page", None)

    tables = [
        "CPE Oprema",
        "CPE Demontirana",
        "CPE Neispravna",
        "Pristupne tehnologije",
        "STB Oprema",
        "IPTV Korisnici",
    ]
    actions = ["login", "logout", "update"]

    return render_template(
        "admin/activity.html",
        logs=logs,
        users=users,
        tables=tables,
        actions=actions,
        pagination_args=args,
    )
