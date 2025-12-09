import os
from flask import Flask, render_template, redirect, url_for, request, flash
from sqlalchemy import func, text
from models import (
    db,
    CpeRecords,
    CpeInventory,
    CpeDismantle,
    Users,
    Cities,
    CpeTypes,
    DismantleTypes,
    CPE_TYPE_CHOICES,
)
from datetime import date, timedelta
import datetime
from flask_login import (
    LoginManager,
    login_required,
    login_user,
    logout_user,
    current_user,
)
from werkzeug.security import check_password_hash, generate_password_hash

# --Import the command function and register it ---
from create_admin_cli import create_initial_admin
from create_db_tables_cli import create_initial_db

DB_HOST = os.environ.get("DB_HOST", "localhost")
# KADA NAPRAVIMO python app.py UNUTAR MOG VS CODA, ODNOSNO IZ VANA
# DOCKER MREZE GADJAMO DOKERIZOVANI POSTGRES 5431
# MEDJUTIM KADA DOKERIZUJEMO FLASK APP MI SMO U INTERNOM DOCKER
# OKRUZENJU I ONDA TREBA DA GADJAMAO 5342
DB_PORT = os.environ.get("DB_PORT", "5431")  # <-- add port variable
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASS = os.environ.get("DB_PASSWORD", "mypassword")
DB_NAME = os.environ.get("DB_NAME", "mydb")

# -----------DEFINE APP OBJECT---------------

SQLALCHEMY_DATABASE_URI = (
    f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# Flask-login uses sessions to store temporary, user-specific data
# (like the logged-in user's ID). To ensure this data can't be tampered with
# by clients, Flask requires a SECRET_KEY to cryptographically sign the
# session cookie.
app.config["SECRET_KEY"] = "a_very_long_and_random_string_for_security"

# ----- INICIALIZE---------


# Initialize SQLAlchemy with the app
db.init_app(app)

# --- Initialize Flask-Login ---
login_manager = LoginManager()
login_manager.init_app(app)
# Optional: Set the view function name for the login page
login_manager.login_view = "login"


# While you defined the User model, you haven't yet registered the required user_loader
# callback function with Flask-Login in your app.py. This function is absolutely mandatory
# for Flask-Login to work.
# The user_loader callback is a function that takes a user ID (as a string)
# and returns the corresponding user object from your database,
# or None if the ID is invalid.
@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))


# Register the command function with the Flask CLI
app.cli.add_command(create_initial_admin)
app.cli.add_command(create_initial_db)

# ---------------HELPER FUNCTION--------------------------

SQL_QUERY = """
SELECT
	c.name AS city_name,
	p.*, 
	max_ts.max_updated_at 
FROM
	(	
		SELECT * 
		FROM crosstab(
			$$
			SELECT 
				city_id,
			    cpe_model,
			    quantity
			FROM
				(
					SELECT 
						r.city_id,
						s.name AS cpe_model,
						r.quantity,
						r.updated_at,
						ROW_NUMBER() OVER(
							PARTITION BY r.city_id, r.cpe_type_id
							ORDER BY r.updated_at DESC
						) AS rn
					FROM cpe_inventory r
					JOIN cpe_types s ON r.cpe_type_id=s.id
				) AS ranked_records
			WHERE
				rn=1
			ORDER BY
			    city_id,
			    cpe_model
			$$
		) AS pivot_table ( 
		city_id INTEGER, "H267N/HG658V2/Zyxel/Skyworth" int, "Arris VIP4205/VIP4302" int, "Arris VIP5305" int,"EKT DIN4805V 4K" int, "EKT DIN7005V HD" int, "Skyworth HP44H HD/4K" int, "ONT HUAWEI" int, "ONT NOKIA" int, "STB DTH" int, "ANTENA SATELITSKA DTH" int,"LNB DUO TWIN" int   
		)
	)AS p
JOIN cities c ON c.id=p.city_id
LEFT JOIN (
	SELECT 
		city_id,
		MAX(updated_at) AS max_updated_at
	FROM cpe_inventory
	GROUP BY
		city_id
) AS max_ts ON max_ts.city_id=p.city_id; 
"""


# Function to get the latest CPE records for all cities
def get_latest_cpe_records():
    # Subquery: find latest updated_at per city
    # Select two fields:
    # the city id
    # the maximum updated_at for that city
    # SELECT MAX(updated_at)
    subquery = (
        db.session.query(
            CpeRecords.city_id, func.max(CpeRecords.updated_at).label("max_date")
        )
        # This finds the newest date for each city.
        # Group results by each city, so every city returns one row
        .group_by(CpeRecords.city_id)
        # Wrap the result as a subquery, so we can join it later.
        .subquery()
    )

    # Join with real records to get the newest row, we want also all fields
    latest_records = (
        db.session.query(CpeRecords)
        .join(
            subquery,
            (CpeRecords.city_id == subquery.c.city_id)
            & (CpeRecords.updated_at == subquery.c.max_date),
        )
        .order_by(CpeRecords.city_id)
        .all()
    )

    totals = {
        "iads": 0,
        "stb_arr_4205": 0,
        "stb_arr_5305": 0,
        "stb_ekt_4805": 0,
        "stb_ekt_7005": 0,
        "stb_sky_44h": 0,
        "ont_huaw": 0,
        "ont_nok": 0,
        "stb_dth": 0,
        "antena_dth": 0,
        "lnb_duo": 0,
    }

    for r in latest_records:
        totals["iads"] += r.iads
        totals["stb_arr_4205"] += r.stb_arr_4205
        totals["stb_arr_5305"] += r.stb_arr_5305
        totals["stb_ekt_4805"] += r.stb_ekt_4805
        totals["stb_ekt_7005"] += r.stb_ekt_7005
        totals["stb_sky_44h"] += r.stb_sky_44h
        totals["ont_huaw"] += r.ont_huaw
        totals["ont_nok"] += r.ont_nok
        totals["stb_dth"] += r.stb_dth
        totals["antena_dth"] += r.antena_dth
        totals["lnb_duo"] += r.lnb_duo

    return latest_records, totals


# AUTHORIZATION ZA BILO KOJU AKCIJU: SAMO ADMIN
def admin_required():
    if current_user.is_authenticated and current_user.role == "admin":
        return True
    flash("Niste Autorizovani!", "danger")
    return False


# AUTHORIZACIJA ZA CPECIFICNU AKCIJU: ILI ADMIN ILI USER AKO JE NJEGOV RESURS
# The helper function admin_and_user_required(city_id) handles access based
# on role ("admin") or resource ownership (current_user.city_id == city_id).
def admin_and_user_required(city_id):
    try:
        user_city_id = str(current_user.city_id)
        requested_city_id = str(city_id)
    except Exception:
        flash("Greška u provjeri autorizacije!", "danger")
        return False
    if current_user.is_authenticated and (
        user_city_id == requested_city_id or current_user.role == "admin"
    ):
        return True
    flash("Niste Autorizovani!", "danger")
    return False


def get_latest_pivoted_inventory():
    # 1. Prepare the raw SQL string
    sql_statement = text(SQL_QUERY)

    # 2. Execute the query
    result = db.session.execute(sql_statement)

    # 3. Fetch all rows
    # The result is a ResultProxy; .mappings() helps convert rows to dicts
    # for easier handling in a web app.
    pivoted_data = [row._asdict() for row in result.all()]

    return pivoted_data


# AUTHORIZATION ZA VIEW: ILI ADMIN ILI VIEW
def view_required():
    if current_user.is_authenticated and (
        current_user.role == "view" or current_user.role == "admin"
    ):
        return True
    flash("Niste Autorizovani!", "danger")
    return False


# -------------------------------------------------------


# -------------------------------- ROUTES------
# HOME PAGE
@app.route("/")
@login_required  # <-- This is the protection decorator!
def home():
    today = date.today()
    # today.weekday() gives 0 for Monday, 6 for Sunday
    # Subtracting gives the date for this week's Monday
    monday = today - timedelta(days=today.weekday())  # Monday of this week
    # Initialize totals to None
    totals = None
    if current_user.role == "admin" or current_user.role == "view":
        # ZA ADMIN USERA DOBAVI POSLJEDNJI DATUM ZA SVAKI GRAD
        records, totals = get_latest_cpe_records()
    else:
        # ZA NE ADMI USERA POSALJI ISTORIJSKU PAGINACIJU ZA TAJ GRAD
        page = request.args.get("page", 1, type=int)
        per_page = 10
        records = (
            CpeRecords.query.filter_by(city_id=current_user.city_id)
            .order_by(CpeRecords.updated_at.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
    return render_template(
        "home.html",
        records=records,
        totals=totals,
        today=today.strftime("%d-%m-%Y"),
        monday=monday,
    )


@app.route("/cpe-data")
@login_required
def getcpe():
    records = get_latest_pivoted_inventory()
    print(records)
    return render_template("cpe.html", records=records)


# ADMIN DASHBOARD PAGE
@app.route("/admin/")
@login_required
def admin_dashboard():
    return render_template("admin.html")


# UPDATE ROUTE HOME TABLE, CALLED FROM INSIDE UPDATE FORM
@app.route("/update_cpe", methods=["POST"])
@login_required
def update_cpe():
    # 1. Extract and Convert Fields
    city_id = request.form.get("city_id")  # <-- GET THE HIDDEN ID
    if not city_id:
        flash("City ID is missing.", "danger")
        return redirect(url_for("home"))

    if not admin_and_user_required(city_id):
        return redirect(url_for("home"))

    current_date = date.today()

    # maybe validate fields
    # construct NEW Cperecord object
    # Extract CPE fields and safely convert to integer (or use validation library like WTForms)
    # Extract CPE fields and safely convert to integer (or use validation library like WTForms)
    cpe_data = {
        "iads": int(request.form.get("iads", 0)),
        "stb_arr_4205": int(request.form.get("stb_arr_4205", 0)),
        "stb_arr_5305": int(request.form.get("stb_arr_5305", 0)),
        "stb_ekt_4805": int(request.form.get("stb_ekt_4805", 0)),
        "stb_ekt_7005": int(request.form.get("stb_ekt_7005", 0)),
        "stb_sky_44h": int(request.form.get("stb_sky_44h", 0)),
        "ont_huaw": int(request.form.get("ont_huaw", 0)),
        "ont_nok": int(request.form.get("ont_nok", 0)),
        "stb_dth": int(request.form.get("stb_dth", 0)),
        "antena_dth": int(request.form.get("antena_dth", 0)),
        "lnb_duo": int(request.form.get("lnb_duo", 0)),
    }

    # 2. Query for Existing Record
    existing_record = (
        db.session.query(CpeRecords)
        .filter(
            CpeRecords.city_id == city_id,
            # Cast the TIMESTAMP column (updated_at) to DATE for a correct comparison
            func.date(CpeRecords.updated_at) == current_date,
        )
        .first()
    )

    # 3. Handle Update vs. Create Logic
    if existing_record:
        # if city_id and  updated_at combination already exsist just update exsisting row
        for key, value in cpe_data.items():
            setattr(existing_record, key, value)
        # Update the timestamp
        existing_record.updated_at = datetime.datetime.now()
        flash("Postojeći unos ažuriran!", "success")
    else:
        # --- CREATE LOGIC ---
        # If record does NOT exist, create a new one
        # if not append new row in Cperecordes table for city and Date
        new_cpe_record = CpeRecords(
            city_id=city_id,
            **cpe_data,
        )

        db.session.add(new_cpe_record)
        flash("Novi unos kreiran!", "success")

    db.session.commit()

    # 4. Redirect to Home (Post-Redirect-Get Pattern)
    # This prevents duplicate form submissions if the user hits refresh.
    return redirect(url_for("home"))


# AUTENTIFIKACIJA
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = Users.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            # Flask will store user session in browser
            login_user(user)  # from flask-login packet
            flash(f"Dobrodošli, {username}", "success")
            return redirect(url_for("home"))
        flash("Invalid credentials", "danger")
        return render_template("login.html", message="Invalid credentials")

    return render_template("login.html")


# LOGGOUT
@app.route("/logout")
@login_required
def logout():
    username_to_flash = current_user.username
    logout_user()
    flash(f"Doviđenja, {username_to_flash}", "success")
    return redirect(url_for("login"))


# -----------------CITIES CRUD---------------------
@app.route("/admin/cities")
@login_required
def admin_cities():
    if not view_required():
        # return "Forbidden", 403
        return redirect(url_for("admin_dashboard"))

    cities = Cities.query.order_by(Cities.id).all()
    return render_template("admin/cities.html", cities=cities)


@app.route("/admin/cities/add", methods=["GET", "POST"])
@login_required
def admin_add_city():
    if not admin_required():
        return redirect(url_for("admin_cities"))

    # THIS IS FOR SUMBITING REQUEST
    if request.method == "POST":
        name = request.form.get("name")
        type = request.form.get("type")

        # Validation: name must be unique
        existing_city = Cities.query.filter_by(name=name).first()
        if existing_city:
            flash("Skladište već postoji", "danger")
            return redirect(url_for("admin_add_city"))

        db.session.add(Cities(name=name, type=type))
        db.session.commit()
        return redirect(url_for("admin_cities"))

    types = db.session.query(Cities.type).distinct().all()
    types = [t[0] for t in types]  # flatten list of tuples
    # THIS IS FOR GET REQUEST WHEN OPENING ADD FORM
    return render_template("admin/cities_add.html", types=types)


@app.route("/admin/cities/edit/<int:id>", methods=["GET", "POST"])
@login_required
def admin_edit_city(id):
    if not admin_required():
        return redirect(url_for("admin_cities"))

    city = Cities.query.get_or_404(id)

    types = db.session.query(Cities.type).distinct().all()
    types = [t[0] for t in types]

    if request.method == "POST":
        city.name = request.form.get("name")
        city.type = request.form.get("type")
        db.session.commit()
        return redirect(url_for("admin_cities"))

    return render_template("admin/cities_edit.html", city=city, types=types)


@app.route("/admin/cities/delete/<int:id>")
@login_required
def admin_delete_city(id):
    if not admin_required():
        return redirect(url_for("admin_cities"))

    city = Cities.query.get_or_404(id)

    # PROTECT CITY DELETE: block if related rows exist
    if city.cpe_records or city.users:
        flash("Cannot delete this city because it has related data.", "danger")
        return render_template(
            "admin/cities_list.html",
            cities=Cities.query.all(),
        )
    flash("City deleted!", "success")
    db.session.delete(city)
    db.session.commit()
    return redirect(url_for("admin_cities"))


# ------------------USERS CRUD-----------------------------------------
@app.route("/admin/users")
@login_required
def admin_users():
    if not view_required():
        # return "Forbidden", 403
        return redirect(url_for("admin_dashboard"))
    users = Users.query.order_by(Users.id).all()
    return render_template("admin/users.html", users=users)


@app.route("/admin/users/add", methods=["GET", "POST"])
@login_required  # AUTHENTICATE
def admin_add_user():
    if not admin_required():  # AUTHORIZE
        return redirect(url_for("admin_users"))

    # THIS IS FOR SUMBITING A NEW REQUEST
    if request.method == "POST":
        username = request.form.get("username")
        plain_password = request.form.get("password")
        # CHOOSED FROM SELECTION IN ADD FORM
        city_id = request.form.get("city_id", type=int)
        # CHOOSED FROM SELECTION IN ADD FORM
        role = request.form.get("role")

        # Validation: username must be unique
        existing_user = Users.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already exists", "danger")
            return redirect(url_for("admin_add_user"))

        # Validation: city must be real (if provided)
        if city_id:
            city = Cities.query.get(city_id)
            if not city:
                flash("Invalid city selected", "danger")
                return redirect(url_for("admin_add_user"))

        # Validation: role must be valid
        if role not in ["admin", "user", "view"]:
            flash("Invalid role", "danger")
            return redirect(url_for("admin_add_user"))

        password_hash = generate_password_hash(plain_password)

        user = Users(
            username=username,
            password_hash=password_hash,
            city_id=city_id,
            role=role,
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
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

    cities = Cities.query.order_by(Cities.name).all()
    roles = db.session.query(Users.role).distinct().all()
    roles = [r[0] for r in roles]  # flatten list of tuples

    # THIS IS FOR GET REQUEST WHEN OPENING BLANK ADD FORM
    return render_template("admin/users_add.html", cities=cities, roles=roles)


@app.route("/admin/users/edit/<int:id>", methods=["GET", "POST"])
@login_required
def admin_edit_user(id):
    if not admin_required():
        return redirect(url_for("admin_users"))

    user = Users.query.get_or_404(id)

    cities = Cities.query.order_by(Cities.name).all()
    roles = db.session.query(Users.role).distinct().all()
    roles = [r[0] for r in roles]  # flatten list of tuples

    if request.method == "POST":
        username = request.form.get("username")
        plain_password1 = request.form.get("password1")
        plain_password2 = request.form.get("password2")
        # CHOOSED FROM SELECTION IN ADD FORM
        city_id = request.form.get("city_id", type=int)
        # CHOOSED FROM SELECTION IN ADD FORM
        role = request.form.get("role")

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

        # Validation: city must be real (if provided)
        if city_id:
            city = Cities.query.get(city_id)
            if not city:
                flash("Invalid city selected", "danger")
                return redirect(url_for("admin_edit_user", id=id))

        # Validation: role must be valid
        if role not in roles:
            flash("Invalid role", "danger")
            return redirect(url_for("admin_edit_user", id=id))

        # Prevent Admin from Demoting Themselves
        if current_user.id == user.id and user.role == "admin" and role != "admin":
            flash("Ne možete ukloniti svoju admin ulogu!", "danger")
            return redirect(url_for("admin_edit_user", id=id))

        user.username = username
        user.city_id = city_id
        user.role = role
        user.updated_at = datetime.datetime.now()

        try:
            db.session.commit()
            flash("Korisnik uspješno izmijenjen!", "success")
            return redirect(url_for("admin_users"))
        except Exception as e:
            db.session.rollback()
            flash(f"Greška prilikom izmjene korisnika: {e}", "danger")
            return redirect(url_for("admin_edit_user", id=id))

    return render_template(
        "admin/users_edit.html", user=user, roles=roles, cities=cities
    )


@app.route("/admin/users/delete/<int:id>")
@login_required
def admin_delete_user(id):
    if not admin_required():
        return redirect(url_for("admin_users"))

    user = Users.query.get_or_404(id)

    if user.role == "admin":
        admin_count = Users.query.filter_by(role="admin").count()
        if admin_count:
            flash("Ne možete obrisati posljednjeg admina!", "danger")
            return redirect(url_for("admin_users"))

    db.session.delete(user)
    db.session.commit()
    flash("User deleted", "success")
    return redirect(url_for("admin_users"))


# -------------CPE_INVENTORY CRUD----------------------------------------
@app.route("/admin/cpe_inventory")
@login_required
def admin_cpe_inventory():
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
    return render_template(
        "admin/cpe_inventory.html",
        records=pagination.items,
        pagination=pagination,
        sort_by=sort_by,
        direction=direction,
    )


# -------------CPE_DISMANTLE_RECORDS CRUD----------------------------------------
@app.route("/admin/cpe_dismantle")
@login_required
def admin_cpe_dismantle():
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


# -----------------CPE_TYPES CRUD---------------------
@app.route("/admin/cpe_types")
@login_required
def admin_cpe_types():
    if not view_required():
        # return "Forbidden", 403
        return redirect(url_for("admin_dashboard"))
    cpes = CpeTypes.query.order_by(CpeTypes.id).all()
    return render_template("admin/cpe_types.html", cpes=cpes)


@app.route("/admin/cpe_types/add", methods=["GET", "POST"])
@login_required
def admin_add_cpe_type():
    if not admin_required():
        return redirect(url_for("admin_cpe_types"))

    # THIS IS FOR SUMBITING REQUEST
    if request.method == "POST":
        name = request.form.get("name")
        label = request.form.get("label")
        type = request.form.get("type")

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
    types = CPE_TYPE_CHOICES

    # THIS IS FOR GET REQUEST WHEN INICIALY OPENING ADD FORM
    return render_template("admin/cpe_types_add.html", types=types)


@app.route("/admin/cpe_types/edit/<int:id>", methods=["GET", "POST"])
@login_required
def admin_edit_cpe_type(id):
    if not admin_required():
        return redirect(url_for("admin_cpe_types"))

    cpe = CpeTypes.query.get_or_404(id)

    types = CPE_TYPE_CHOICES

    if request.method == "POST":
        name = request.form.get("name")
        label = request.form.get("label")
        type_ = request.form.get("type")  # renamed to avoid shadowing built-in 'type'
        is_active = request.form.get("is_active")

        # Username uniqueness (except current user)
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
        cpe.is_active = "is_active" in request.form  # THIS IS THE CORRECT WAY

        try:
            db.session.commit()
            flash("Cpe tip uspješno izmijenjen!", "success")
            return redirect(url_for("admin_cpe_types"))
        except Exception as e:
            db.session.rollback()
            flash(f"Greška prilikom izmjene korisnika: {e}", "danger")
            return redirect(url_for("admin_edit_cpe_type", id=id))

    return render_template(
        "admin/cpe_types_edit.html",
        cpe=cpe,
        types=types,
    )


# -----------------DISMANTLE TYPES CRUD---------------------
@app.route("/admin/dismantle_status")
@login_required
def admin_dismantle_status():
    if not view_required():
        # return "Forbidden", 403
        return redirect(url_for("admin_dashboard"))
    status = DismantleTypes.query.order_by(DismantleTypes.id).all()
    return render_template("admin/dismantle_types.html", status=status)


# -----MAIN LOOP-----------
# Only needed for local development
# python app.py
# During production, your Dockerfile runs Gunicorn instead,
# so that block never executes.
if __name__ == "__main__":
    app.run(debug=True)  # <-- This enables the reloader and debugger
