import os
from flask import Flask, render_template, redirect, url_for, request
from sqlalchemy import func
from models import db, CpeRecords, Users, Cities
from datetime import date
import datetime


from flask_login import (
    LoginManager,
    login_required,
    login_user,
    logout_user,
    current_user,
)
from werkzeug.security import check_password_hash

# --Import the command function and register it ---
from create_admin_cli import create_initial_admin

DB_HOST = os.environ.get("DB_HOST", "localhost")
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

# ---------------HELPER FUNCTION--------------------------


# Function to get the latest CPE records for all cities
def get_latest_cpe_records():
    # Subquery: find latest record_date per city
    # Select two fields:
    # the city id
    # the maximum record_date for that city
    # SELECT MAX(record_date)
    subquery = (
        db.session.query(
            CpeRecords.city_id, func.max(CpeRecords.record_date).label("max_date")
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
            & (CpeRecords.record_date == subquery.c.max_date),
        )
        .order_by(CpeRecords.city_id)
        .all()
    )
    return latest_records


# -------------------------------------------------------


# -------------------------------- ROUTES------
@app.route("/")
@login_required  # <-- This is the protection decorator!
def home():
    latest_records = get_latest_cpe_records()
    today = date.today().strftime("%d-%m-%Y")
    return render_template("home.html", records=latest_records, today=today)


@app.route("/update_cpe", methods=["POST"])
@login_required
def update_cpe():
    # 1. Extract and Convert Fields
    city_id = request.form.get("city_id")  # <-- GET THE HIDDEN ID
    current_date = date.today()

    # Check if city_id is missing or invalid
    if not city_id:
        return "Error: City ID is missing.", 400

    # maybe validate fields
    # construct NEW Cperecord object
    # Extract CPE fields and safely convert to integer (or use validation library like WTForms)
    # Extract CPE fields and safely convert to integer (or use validation library like WTForms)
    cpe_data = {
        "iad267": int(request.form.get("iad267", 0)),
        "stb_arr_4205": int(request.form.get("stb_arr_4205", 0)),
        "stb_arr_5305": int(request.form.get("stb_arr_5305", 0)),
        "stb_ekt_4805": int(request.form.get("stb_ekt_4805", 0)),
        "stb_ekt_7005": int(request.form.get("stb_ekt_7005", 0)),
        "stb_sky_44": int(request.form.get("stb_sky_44", 0)),
        "ont_hw": int(request.form.get("ont_hw", 0)),
        "ont_no": int(request.form.get("ont_no", 0)),
        "dth": int(request.form.get("dth", 0)),
        "antena": int(request.form.get("antena", 0)),
        "lnb": int(request.form.get("lnb", 0)),
    }

    # 2. Query for Existing Record
    existing_record = (
        db.session.query(CpeRecords)
        .filter(CpeRecords.city_id == city_id, CpeRecords.record_date == current_date)
        .first()
    )

    # 3. Handle Update vs. Create Logic
    if existing_record:
        # if city_id and  record_date combination already exsist just update exsisting row
        for key, value in cpe_data.items():
            setattr(existing_record, key, value)
        # Update the timestamp
        existing_record.created_at = datetime.datetime.now()
    else:
        # --- CREATE LOGIC ---
        # If record does NOT exist, create a new one
        # if not append new row in Cperecordes table for city and Date
        new_cpe_record = CpeRecords(
            city_id=city_id,
            record_date=current_date,  # Use today's date
            created_at=datetime.datetime.now(),
            **cpe_data,
        )
        db.session.add(new_cpe_record)
    db.session.commit()

    # 4. Redirect to Home (Post-Redirect-Get Pattern)
    # This prevents duplicate form submissions if the user hits refresh.
    return redirect(url_for("home"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = Users.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            # Flask will store user session in browser
            login_user(user)
            return redirect(url_for("home"))
        return render_template("login.html", message="Invalid credentials")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# AUTHORIZATION
def admin_required():
    if not current_user.is_authenticated or current_user.role != "admin":
        return False
    return True


@app.route("/admin/")
@login_required
def admin_dashboard():
    return render_template("admin.html")


# ---CITIES CRUD----
@app.route("/admin/cities")
@login_required
def admin_cities():
    if not admin_required():
        return "Forbidden", 403
    cities = Cities.query.order_by(Cities.id).all()
    return render_template("admin/cities_list.html", cities=cities)


@app.route("/admin/cities/add", methods=["GET", "POST"])
@login_required
def admin_add_city():
    if not admin_required():
        return "Forbidden", 403

    # THIS IS FOR SUMBITING REQUEST
    if request.method == "POST":
        name = request.form.get("name")
        db.session.add(Cities(name=name))
        db.session.commit()
        return redirect(url_for("admin_cities"))

    # THIS IS FOR GET REQUEST WHEN OPENING ADD FORM
    return render_template("admin/cities_add.html")


@app.route("/admin/cities/edit/<int:id>", methods=["GET", "POST"])
@login_required
def admin_edit_city(id):
    if not admin_required():
        return "Forbidden", 403

    city = Cities.query.get_or_404(id)

    if request.method == "POST":
        city.name = request.form.get("name")
        db.session.commit()
        return redirect(url_for("admin_cities"))

    return render_template("admin/cities_edit.html", city=city)


@app.route("/admin/cities/delete/<int:id>")
@login_required
def admin_delete_city(id):
    if not admin_required():
        return "Forbidden", 403

    city = Cities.query.get_or_404(id)

    # PROTECT CITY DELETE: block if related rows exist
    if city.cpe_records or city.users:
        return render_template(
            "admin/cities_list.html",
            cities=Cities.query.all(),
            error="Cannot delete this city because it has related data.",
        )

    db.session.delete(city)
    db.session.commit()
    return redirect(url_for("admin_cities"))


# ---USERS CRUD----
@app.route("/admin/users")
@login_required
def admin_users():
    pass


# ---CPE RECORDS CRUD----
@app.route("/admin/cpe_records")
@login_required
def admin_cpe_records():
    # THIS REQUEST ARG WE ARE GETTING FROM TEMPLATE <a LINK:
    # href="{{ url_for('admin_cpe_records', page=pagination.next_num, sort=sort_by, direction=direction) }}"
    page = request.args.get("page", 1, type=int)
    per_page = 50

    sort_by = request.args.get("sort", "id")
    direction = request.args.get("direction", "asc")

    # Whitelist allowed sort columns (prevents SQL injection)
    allowed_sorts = ["id", "record_date", "created_at"]
    if sort_by not in allowed_sorts:
        sort_by = "id"

    order_column = getattr(CpeRecords, sort_by)
    if direction == "desc":
        order_column = order_column.desc()

    pagination = CpeRecords.query.order_by(order_column).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return render_template(
        "admin/cpe_records_list.html",
        records=pagination.items,
        pagination=pagination,
        sort_by=sort_by,
        direction=direction,
    )


# -----MAIN LOOP-----------
# Only needed for local development
# python app.py
# During production, your Dockerfile runs Gunicorn instead,
# so that block never executes.
if __name__ == "__main__":
    app.run(debug=True)  # <-- This enables the reloader and debugger
