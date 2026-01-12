from datetime import datetime
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user
from sqlalchemy import func
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.utils.permissions import view_required, admin_required
from app.services.admin import get_stb_quantity_chart_data
from app.models import (
    Cities,
    CityTypeEnum,
    CpeDismantle,
    CpeInventory,
    CpeTypeEnum,
    CpeTypes,
    DismantleTypes,
    OntInventory,
    StbInventory,
    StbTypes,
    UserRole,
    Users,
)


admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
)


@admin_bp.route("/cpe_inventory")
@login_required
def cpe_inventory():
    if not view_required():
        # return "Forbidden", 403
        return redirect(url_for("admin_dashboard"))

    # THIS REQUEST ARG WE ARE GETTING FROM TEMPLATE <a LINK:
    # href="{{ url_for('admin_cpe_records', page=pagination.next_num, sort=sort_by, direction=direction) }}"
    page = request.args.get("page", 1, type=int)
    per_page = 50

    # WHEN INCICIALY LANDING ON PAGE
    # DEFAULT VIEW JE SORT BY UPDATE_AT AND DESC, THE MOST RESCENT ON THE TOP
    sort_by = request.args.get("sort", "updated_at")
    direction = request.args.get("direction", "desc")

    # Whitelist allowed sort columns (prevents SQL injection)
    allowed_sorts = ["id", "city_id", "updated_at", "created_at"]
    if sort_by not in allowed_sorts:
        sort_by = "id"

    order_column = getattr(CpeInventory, sort_by)
    if direction == "desc":
        order_column = order_column.desc()

    pagination = CpeInventory.query.order_by(order_column).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # THIS IS DATA FOR NEW CPE MODAL
    # cities = Cities.query.order_by(Cities.id).all()
    # cities = db.session.query(CpeInventory.city_id).distinct().all()

    # Mora biti CpeTypes jer dodajemo novi element u CPEInventory
    # cpe_types = CpeTypes.query.filter_by(is_active_total=True).order_by(CpeTypes.id).all()

    return render_template(
        "admin/cpe_inventory.html",
        records=pagination.items,
        pagination=pagination,
        sort_by=sort_by,
        direction=direction,
        # cities=cities,
        # cpe_types=cpe_types,
    )


@admin_bp.route("/cpe_inventory/add", methods=["POST"])
@login_required
def add_to_cpe_inventory():
    if not admin_required():  # AUTHORIZE
        return redirect(url_for("admin_dashboard"))

    cpe_type_id = request.form.get("cpe_type_id", type=int)

    current_time = datetime.now()
    records_to_add = []

    # --- STEP 1: PRE-FETCH MAX UPDATED_AT FOR ALL CITIES ---
    # This prevents running 10+ separate queries inside the loop.
    max_update_times = (
        db.session.query(
            CpeInventory.city_id, func.max(CpeInventory.updated_at).label("max_time")
        )
        .group_by(CpeInventory.city_id)
        .all()
    )

    # Convert the list of tuples/rows into a dictionary for fast lookup
    # The result is a dictionary: {city_id: max_updated_at, ...}
    max_update_map = {row.city_id: row.max_time for row in max_update_times}

    for key, value in request.form.items():
        if key.startswith("city-"):
            parts = key.split("-", 1)
            if len(parts) == 2:
                city_id_str = parts[1]
                try:
                    city_id = int(city_id_str)
                    quantity = int(value or 0)
                except ValueError:
                    # Skip this record if ID or Quantity is invalid
                    continue

                # --- STEP 3: DETERMINE UPDATED_AT TIMESTAMP ---
                # Use the max timestamp found in STEP 1 for this city.
                # If the city has NO existing records, use the current_time (or NULL, depending on your schema)
                # Using the current time is safer if the city is new or empty.
                latest_update_time = max_update_map.get(city_id, current_time)
                # batch save on every city for selected cpe_type_id
                # FOR EVERY CITY_ID FIND MAX UPDATED_AT

                new_record = CpeInventory(
                    city_id=city_id,
                    cpe_type_id=cpe_type_id,
                    quantity=quantity,
                    created_at=current_time,
                    updated_at=latest_update_time,
                )
            records_to_add.append(new_record)

    # 4. Execute Single Batch Transaction
    if records_to_add:
        try:
            db.session.add_all(records_to_add)
            db.session.commit()
            flash("Novo stanje za CPE inventori uspješno sačuvano!", "success")
        except Exception as e:
            db.session.rollback()
            print(f"Error during CpeInventory batch insert: {e}")
            flash("Došlo je do greške prilikom unosa u bazu.", "danger")
    else:
        flash("Nije pronađen nijedan CPE za unos.", "warning")

    # Redirect to Home (Post-Redirect-Get Pattern)
    # This prevents duplicate form submissions if the user hits refresh.
    return redirect(url_for("admin_cpe_inventory"))


@admin_bp.route("/cpe_dismantle")
@login_required
def cpe_dismantle():
    if not view_required():
        # return "Forbidden", 403
        return redirect(url_for("admin_dashboard"))

    # THIS REQUEST ARG WE ARE GETTING FROM TEMPLATE <a LINK:
    # href="{{ url_for('admin_cpe_records', page=pagination.next_num, sort=sort_by, direction=direction) }}"
    page = request.args.get("page", 1, type=int)
    per_page = 50

    # WHEN INCICIALY LANDING ON PAGE
    # DEFAULT VIEW JE SORT BY UPDATE_AT AND DESC, THE MOST RESCENT ON THE TOP
    sort_by = request.args.get("sort", "updated_at")
    direction = request.args.get("direction", "desc")

    # Whitelist allowed sort columns (prevents SQL injection)
    allowed_sorts = ["id", "city_id", "updated_at", "created_at"]
    if sort_by not in allowed_sorts:
        sort_by = "id"

    order_column = getattr(CpeDismantle, sort_by)
    if direction == "desc":
        order_column = order_column.desc()

    pagination = CpeDismantle.query.order_by(order_column).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return render_template(
        "admin/cpe_dismantle.html",
        records=pagination.items,
        pagination=pagination,
        sort_by=sort_by,
        direction=direction,
    )


@admin_bp.route("/stb_inventory")
@login_required
def stb_inventory():
    if not view_required():
        # return "Forbidden", 403
        return redirect(url_for("admin_dashboard"))

    # THIS REQUEST ARG WE ARE GETTING FROM TEMPLATE <a LINK:
    # href="{{ url_for('admin_cpe_records', page=pagination.next_num, sort=sort_by, direction=direction) }}"
    page = request.args.get("page", 1, type=int)
    per_page = 50

    # WHEN INCICIALY LANDING ON PAGE
    # DEFAULT VIEW JE SORT BY UPDATE_AT AND DESC, THE MOST RESCENT ON THE TOP
    sort_by = request.args.get("sort", "updated_at")
    direction = request.args.get("direction", "desc")

    # Whitelist allowed sort columns (prevents SQL injection)
    allowed_sorts = ["id", "stb_type_id", "week_end", "updated_at", "created_at"]
    if sort_by not in allowed_sorts:
        sort_by = "id"

    order_column = getattr(StbInventory, sort_by)
    if direction == "desc":
        order_column = order_column.desc()

    pagination = StbInventory.query.order_by(order_column).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # THIS IS DATA FOR NEW CPE MODAL
    # Mora biti CpeTypes jer dodajemo novi element u CPEInventory
    stb_types = StbTypes.query.filter_by(is_active=True).order_by(StbTypes.id).all()

    return render_template(
        "admin/stb_inventory.html",
        records=pagination.items,
        pagination=pagination,
        sort_by=sort_by,
        direction=direction,
        stb_types=stb_types,
    )


@admin_bp.route("/ont_inventory")
@login_required
def ont_inventory():
    if not view_required():
        # return "Forbidden", 403
        return redirect(url_for("admin_dashboard"))

    # THIS REQUEST ARG WE ARE GETTING FROM TEMPLATE <a LINK:
    # href="{{ url_for('admin_cpe_records', page=pagination.next_num, sort=sort_by, direction=direction) }}"
    page = request.args.get("page", 1, type=int)
    per_page = 50

    # WHEN INCICIALY LANDING ON PAGE
    # DEFAULT VIEW JE SORT BY UPDATE_AT AND DESC, THE MOST RESCENT ON THE TOP
    sort_by = request.args.get("sort", "updated_at")
    direction = request.args.get("direction", "desc")

    # Whitelist allowed sort columns (prevents SQL injection)
    allowed_sorts = ["id", "city_id", "updated_at", "created_at"]
    if sort_by not in allowed_sorts:
        sort_by = "id"

    order_column = getattr(OntInventory, sort_by)
    if direction == "desc":
        order_column = order_column.desc()

    pagination = OntInventory.query.order_by(order_column).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # THIS IS DATA FOR NEW CPE MODAL
    cities = Cities.query.order_by(Cities.id).all()
    # cities = db.session.query(CpeInventory.city_id).distinct().all()

    return render_template(
        "admin/ont_inventory.html",
        records=pagination.items,
        pagination=pagination,
        sort_by=sort_by,
        direction=direction,
        cities=cities,
    )


###########################################################
# ---------------ROUTES FOR CITIES CRUD--------------------------
############################################################
@admin_bp.route("/cities")
@login_required
def cities():
    if not view_required():
        # return "Forbidden", 403
        return redirect(url_for("admin_dashboard"))

    cities = Cities.query.order_by(Cities.id).all()
    return render_template("admin/cities.html", cities=cities)


@admin_bp.route("/cities/add", methods=["GET", "POST"])
@login_required
def add_city():
    if not admin_required():
        return redirect(url_for("admin.cities"))

    # THIS IS FOR SUMBITING REQUEST
    if request.method == "POST":
        name = request.form.get("name")
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

        db.session.add(Cities(name=name, type=selected_type))
        db.session.commit()
        return redirect(url_for("admin.cities"))

    types = [t.value for t in CityTypeEnum]
    # THIS IS FOR GET REQUEST WHEN OPENING ADD FORM
    return render_template("admin/cities_add.html", types=types)


@admin_bp.route("/cities/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_city(id):
    if not admin_required():
        return redirect(url_for("admin.cities"))

    city = Cities.query.get_or_404(id)

    if request.method == "POST":
        name = request.form.get("name")
        type_string = request.form.get("type")

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

        city.name = name
        city.type = selected_type

        try:
            db.session.commit()
            flash("Skladiste uspješno izmijenjeno!", "success")
            return redirect(url_for("admin.cities", id=id))
        except Exception as e:
            db.session.rollback()
            flash(f"Greška prilikom izmjene: {e}", "danger")
            return redirect(url_for("admin.edit_city", id=id))

    types = [t.value for t in CityTypeEnum]

    return render_template("admin/cities_edit.html", city=city, types=types)


@admin_bp.route("/cities/delete/<int:id>")
@login_required
def delete_city(id):
    if not admin_required():
        return redirect(url_for("admin.cities"))

    city = Cities.query.get_or_404(id)

    # PROTECT CITY DELETE: block if related rows exist

    flash("City deleted!", "success")
    db.session.delete(city)
    db.session.commit()
    return redirect(url_for("admin.cities"))


###########################################################
# ---------------ROUTES FOR USERS CRUD--------------------------
############################################################
@admin_bp.route("/users")
@login_required
def users():
    if not view_required():
        # return "Forbidden", 403
        return redirect(url_for("admin_dashboard"))
    users = Users.query.order_by(Users.id).all()
    return render_template("admin/users.html", users=users)


@admin_bp.route("/users/add", methods=["GET", "POST"])
@login_required  # AUTHENTICATE
def add_user():
    if not admin_required():  # AUTHORIZE
        return redirect(url_for("admin_users"))

    # THIS IS FOR SUMBITING A NEW REQUEST
    if request.method == "POST":
        username = request.form.get("username")
        plain_password = request.form.get("password")
        # CHOOSED FROM SELECTION IN ADD FORM
        city_id = request.form.get("city_id", type=int)
        # CHOOSED FROM SELECTION IN ADD FORM
        role_string = request.form.get("role")

        # 1. Validation: Convert string to Enum object safely
        try:
            selected_role = UserRole(role_string)
        except ValueError:
            flash("Izabrana rola nije važeća.", "danger")
            return redirect(url_for("admin_add_user"))

        # Validation: username must be unique
        existing_user = Users.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already exists", "danger")
            return redirect(url_for("admin_add_user"))

        if selected_role == UserRole.USER and (not city_id or city_id == 0):
            flash("Korisnik sa rolom 'user' mora imati izabran grad.", "danger")
            return redirect(url_for("admin_add_user"))

        password_hash = generate_password_hash(plain_password)

        user = Users(
            username=username,
            password_hash=password_hash,
            city_id=city_id if city_id != 0 else None,
            role=selected_role,  # SQLAlchemy handles the conversion to DB string
        )
        try:
            db.session.add(user)
            db.session.commit()
            flash("User created successfully", "success")
            return redirect(url_for("admin_users"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating user: {e}", "danger")
            return redirect(url_for("admin_add_user"))

    # GET Request
    cities = Cities.query.order_by(Cities.name).all()

    roles = [r.value for r in UserRole]

    # THIS IS FOR GET REQUEST WHEN OPENING BLANK ADD FORM
    return render_template("admin/users_add.html", cities=cities, roles=roles)


@admin_bp.route("/users/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_user(id):
    if not admin_required():
        return redirect(url_for("admin_users"))

    user = Users.query.get_or_404(id)

    if request.method == "POST":
        username = request.form.get("username")
        plain_password1 = request.form.get("password1")
        plain_password2 = request.form.get("password2")
        # CHOOSED FROM SELECTION IN ADD FORM
        city_id = request.form.get("city_id", type=int)
        # CHOOSED FROM SELECTION IN ADD FORM
        role_string = request.form.get("role")

        try:
            selected_role = UserRole(role_string)
        except ValueError:
            flash("Izabrana rola nije važeća.", "danger")
            return redirect(url_for("admin_edit_user", id=id))

        # Username uniqueness (except current user)
        existing_user = Users.query.filter(
            Users.username == username, Users.id != id
        ).first()

        if existing_user:
            flash("Username već postoji!", "danger")
            return redirect(url_for("admin_edit_user", id=id))

        if plain_password1 or plain_password2:
            if plain_password1 != plain_password2:
                flash("Šifre nisu iste!", "danger")
                return redirect(url_for("admin_edit_user", id=id))
            # Update password hash only if a new password is entered
            user.password_hash = generate_password_hash(plain_password1)

        # Prevent Admin from Demoting Themselves
        if (
            current_user.id == user.id
            and user.role == UserRole.ADMIN
            and selected_role != UserRole.ADMIN
        ):
            flash("Ne možete ukloniti svoju admin ulogu!", "danger")
            return redirect(url_for("admin_edit_user", id=id))

        # if role changed to user
        if selected_role == UserRole.USER and (not city_id or city_id == 0):
            flash("Korisnik sa rolom 'user' mora imati izabran grad.", "danger")
            return redirect(url_for("admin_add_user"))

        user.username = username
        user.city_id = city_id if city_id != 0 else None
        user.role = selected_role
        user.updated_at = datetime.now()

        try:
            db.session.commit()
            flash("Korisnik uspješno izmijenjen!", "success")
            return redirect(url_for("admin_users"))
        except Exception as e:
            db.session.rollback()
            flash(f"Greška prilikom izmjene korisnika: {e}", "danger")
            return redirect(url_for("admin_edit_user", id=id))

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
        return redirect(url_for("admin_users"))

    user = Users.query.get_or_404(id)

    if user.role == UserRole.ADMIN:
        admin_count = Users.query.filter_by(role=UserRole.ADMIN).count()
        if admin_count < 2:
            flash("Ne možete obrisati posljednjeg admina!", "danger")
            return redirect(url_for("admin_users"))

    db.session.delete(user)
    db.session.commit()
    flash("User deleted", "success")
    return redirect(url_for("admin_users"))


###########################################################
# ---------------ROUTES FOR CPE TYPES CRUD--------------------------
############################################################
@admin_bp.route("/cpe_types")
@login_required
def cpe_types():
    if not view_required():
        # return "Forbidden", 403
        return redirect(url_for("admin_dashboard"))
    cpes = CpeTypes.query.order_by(CpeTypes.id).all()
    return render_template("admin/cpe_types.html", cpes=cpes)


@admin_bp.route("/cpe_types/add", methods=["GET", "POST"])
@login_required
def add_cpe_type():
    if not admin_required():
        return redirect(url_for("admin_cpe_types"))

    # THIS IS FOR SUMBITING REQUEST
    if request.method == "POST":
        name = request.form.get("name")
        label = request.form.get("label")
        type = request.form.get("type")
        print("type", type)

        # Validation: name must be unique
        existing_cpe_type = CpeTypes.query.filter_by(name=name).first()
        if existing_cpe_type:
            flash("Tip CPE već postoji", "danger")
            return redirect(url_for("admin_add_cpe_type"))

        db.session.add(CpeTypes(name=name, label=label, type=type))
        db.session.commit()
        return redirect(url_for("admin_cpe_types"))

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
        return redirect(url_for("admin_cpe_types"))

    cpe = CpeTypes.query.get_or_404(id)

    types = [member.value for member in CpeTypeEnum]

    if request.method == "POST":
        name = request.form.get("name")
        label = request.form.get("label")
        type_ = request.form.get("type")  # renamed to avoid shadowing built-in 'type'

        # name uniqueness (except current name)
        existing_cpe_type = CpeTypes.query.filter(
            CpeTypes.name == name, CpeTypes.id != id
        ).first()
        if existing_cpe_type:
            flash("Tip CPE opreme već postoji!", "danger")
            return redirect(url_for("admin_edit_cpe_type", id=id))

        # Validation: type must be valid
        if type_ not in types:
            flash("Invalid tip", "danger")
            return redirect(url_for("admin_edit_cpe_type", id=id))

        cpe.id = id
        cpe.name = name
        cpe.label = label
        cpe.type = type_
        cpe.has_remote = "has_remote" in request.form
        cpe.has_adapter = "has_adapter" in request.form
        cpe.is_active_total = "is_active_total" in request.form
        cpe.is_active_dismantle = "is_active_dismantle" in request.form

        try:
            db.session.commit()
            flash("Cpe tip uspješno izmijenjen!", "success")
            return redirect(url_for("admin_cpe_types"))
        except Exception as e:
            db.session.rollback()
            flash(f"Greška prilikom izmjene CPE tipa: {e}", "danger")
            return redirect(url_for("admin_edit_cpe_type", id=id))

    return render_template(
        "admin/cpe_types_edit.html",
        cpe=cpe,
        types=types,
    )


###########################################################
# ---------------ROUTES FOR STB TYPES CRUD--------------------------
############################################################
@admin_bp.route("/stb_types")
@login_required
def stb_types():
    if not view_required():
        # return "Forbidden", 403
        return redirect(url_for("admin_dashboard"))
    stbs = StbTypes.query.order_by(StbTypes.id).all()
    return render_template("admin/stb_types.html", stbs=stbs)


@admin_bp.route("/stb_types/add", methods=["GET", "POST"])
@login_required
def add_stb_type():
    if not admin_required():
        return redirect(url_for("admin_stb_types"))

    # THIS IS FOR SUMBITING REQUEST
    if request.method == "POST":
        name = request.form.get("name")
        label = request.form.get("label")

        # Validation: name must be unique
        existing_stb_type = StbTypes.query.filter_by(name=name).first()
        if existing_stb_type:
            flash("Tip STB već postoji", "danger")
            return redirect(url_for("admin_add_stb_type"))

        db.session.add(StbTypes(name=name, label=label))
        db.session.commit()
        return redirect(url_for("admin_stb_types"))

    # THIS IS FOR GET REQUEST WHEN INICIALY OPENING ADD FORM
    return render_template(
        "admin/stb_types_add.html",
    )


@admin_bp.route("/stb_types/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_stb_type(id):
    if not admin_required():
        return redirect(url_for("admin_stb_types"))

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
            return redirect(url_for("admin_edit_stb_type", id=id))

        stb.id = id
        stb.name = name
        stb.label = label
        stb.is_active = "is_active" in request.form  # THIS IS THE CORRECT WAY

        try:
            db.session.commit()
            flash("Stb tip uspješno izmijenjen!", "success")
            return redirect(url_for("admin_stb_types"))
        except Exception as e:
            db.session.rollback()
            flash(f"Greška prilikom izmjene stb tipa: {e}", "danger")
            return redirect(url_for("admin_edit_stb_type", id=id))

    return render_template("admin/stb_types_edit.html", stb=stb)


###########################################################
# ---------------ROUTES FOR DISMANTLE TYPES CRUD-------------------------
############################################################
@admin_bp.route("/dismantle_status")
@login_required
def dismantle_status():
    if not view_required():
        # return "Forbidden", 403
        return redirect(url_for("admin_dashboard"))
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
# ---------------ROUTES FOR GRAPHICAL-------------------------
############################################################
@admin_bp.route("/stb-dashboard")
@login_required
def stb_dashboard():
    chart_data = get_stb_quantity_chart_data()

    return render_template("charts/stb_dashboard.html", chart_data=chart_data)
