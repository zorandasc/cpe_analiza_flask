import os
from collections import defaultdict
from flask import Flask, render_template, redirect, url_for, request, flash
from sqlalchemy import text, func

# My IMPLEMENTATION OF PAGINATION FUNCIONALITY
# FOR PAGINATING RAW PIVOTED SQL STATEMENT
from simplepagination import SimplePagination

from models import (
    db,
    CpeInventory,
    CpeDismantle,
    StbInventory,
    OntInventory,
    Users,
    Cities,
    CpeTypes,
    StbTypes,
    DismantleTypes,
    CpeTypeEnum,
    CityTypeEnum,
    UserRole,
)
from datetime import date, timedelta, datetime
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
# KADA NAPRAVIMO python app.py UNUTAR VS CODA, ODNOSNO IZ VANA
# DOCKER MREZE, GADJAMO DOKERIZOVANI POSTGRES 5431
# MEDJUTIM KADA DOKERIZUJEMO FLASK APP MI SMO U INTERNOM DOCKER
# OKRUZENJU I ONDA TREBA DA GADJAMAO 5342, ODNOSNO
# DB_PORT: 5432 U DOCKER COMPOSE
DB_PORT = os.environ.get("DB_PORT", "5431")
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


# SINGLE SOURCE OF TRUTH FOR WHOLE CPE-RECORDS TABLE
# THIS IS LIST OF FULL CPETYPE OBJECTS, BUT ONLY IF is_active
# FROM THIS SCHEMA LIST:
# 1. WE USE IT TO BUILD RAW DYNAMIC PIVOT SQL QUERY
# 2. WE ALSO USE IT IN HTML TABLES TEMPLATES DIS
# PLAY
def get_cpe_types_column_schema(column_name: str = "is_active_total"):
    filter_column = getattr(CpeTypes, column_name)
    # 2. Get full data (id, name, label, type) from Cpe_Types table
    cpe_types = (
        db.session.query(CpeTypes.id, CpeTypes.name, CpeTypes.label, CpeTypes.type)
        .filter(filter_column)
        .order_by(CpeTypes.id)
        .all()
    )

    # Prepare the structured list and separate lists
    schema_list = [
        {"id": id, "name": name, "label": label, "cpe_type": type}
        for id, name, label, type in cpe_types
    ]

    return schema_list


def get_pivoted_cpe_inventory(schema_list: list, week_end: datetime.date):
    if not schema_list:
        # Return empty data lists immediately if no active CPE types are found
        return []

    case_columns = []
    sum_columns = []

    for model in schema_list:
        case_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN cpe_name = '{model["name"]}' THEN quantity END),
                0
            ) AS "{model["name"]}"
            """
        )
        sum_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN cpe_name = '{model["name"]}' THEN quantity END),
                0
            ) AS "{model["name"]}"
            """
        )

    SQL_QUERY = f"""
        WITH weekly_data AS (
            SELECT
                c.id   AS city_id,
                c.name AS city_name,
                ct.name AS cpe_name,
                ci.quantity AS quantity,
                ci.updated_at AS updated_at
            FROM cities c
            LEFT JOIN cpe_inventory ci
                ON c.id = ci.city_id
                --Use the latest available record whose week_end is ≤ current business Friday
                --Give me the latest week if we are in new week which doesnot have data yet
                AND ci.week_end =(
                SELECT MAX(ci2.week_end)
                FROM cpe_inventory ci2
                WHERE ci2.city_id=c.id
                AND ci2.week_end <= :week_end
                )
            LEFT JOIN cpe_types ct
                ON ct.id = ci.cpe_type_id
        )
        SELECT
            city_id,
            city_name,
            {", ".join(case_columns)},
            MAX(updated_at) AS max_updated_at
        FROM weekly_data
        GROUP BY city_id, city_name

        UNION ALL

        SELECT
            NULL,
            'UKUPNO',
            {", ".join(sum_columns)},
            NULL
        FROM weekly_data

        ORDER BY city_id NULLS LAST;
    """

    params = {"week_end": week_end}

    result = db.session.execute(text(SQL_QUERY), params)
    return [row._asdict() for row in result.all()]


def get_city_history_cpe_inventory(
    city_id: int, schema_list: list, page: int, per_page: int
):
    """
    Retrieves the historical records for a specific city_id, pivoted by CPE type.
    This query handles pagination internally based on the unique WEEK_END timestamp.
    """
    if not schema_list:
        # Return empty data lists immediately if no active CPE types are found
        return []

    # We need a separate query to get the total count for pagination
    count_query = text(
        """SELECT 
                COUNT(DISTINCT WEEK_END) 
            FROM CPE_INVENTORY 
            WHERE CITY_ID=:city_id
        """
    )

    total_count = db.session.execute(count_query, {"city_id": city_id}).scalar()

    # Calculate offset
    offset = (page - 1) * per_page

    case_columns = []

    for model in schema_list:
        case_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN ct.name = '{model["name"]}' THEN ci.quantity END),
                0
            ) AS "{model["name"]}"
            """
        )

    SQL_QUERY = f"""
        SELECT
            WEEK_END,
            {", ".join(case_columns)}
        FROM cpe_inventory ci
        LEFT JOIN cpe_types ct ON ct.id=ci.cpe_type_id
        WHERE ci.city_id = :city_id
        GROUP BY ci.WEEK_END
        ORDER BY ci.week_end DESC
        LIMIT :limit
        OFFSET :offset
    """

    params = {
        "city_id": city_id,
        "limit": per_page,
        "offset": offset,
    }

    result = db.session.execute(text(SQL_QUERY), params)

    # pivoted_data is now list
    pivoted_data = [row._asdict() for row in result.all()]

    # paginate is iterable SimplePagination object
    paginate = SimplePagination(
        page=page, per_page=per_page, total=total_count, items=pivoted_data
    )

    return paginate


# SQL responsibilities: Fetch latest week, Aggregate per city
# Produce totals per dismantle type
# Python responsibilities: Split result set by dismantle_type_id,
# Render:Complete table, Missing parts table (nested headers)
def get_pivoted_cpe_dismantle(
    schema_list: list, week_end: datetime.date, city_type: str
):
    if not schema_list:
        # Return empty data lists immediately if no active CPE types are found
        return []

    case_columns = []
    sum_columns = []

    for model in schema_list:
        case_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN cpe_name = '{model["name"]}' THEN quantity END),
                0
            ) AS "{model["name"]}"
            """
        )
        sum_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN cpe_name = '{model["name"]}' THEN quantity END),
                0
            ) AS "{model["name"]}"
            """
        )

    SQL_QUERY = f"""
                WITH WEEKLY_DATA AS (
                SELECT
                    C.ID AS CITY_ID,
                    C.NAME AS CITY_NAME,
                    CT.NAME AS CPE_NAME,
                    CD.QUANTITY,
                    CD.DISMANTLE_TYPE_ID,
                    CD.UPDATED_AT
                FROM CITIES C
                LEFT JOIN CPE_DISMANTLE CD
                    ON C.ID = CD.CITY_ID
                    AND CD.WEEK_END = (
                        SELECT MAX(CD2.WEEK_END)
                        FROM CPE_DISMANTLE CD2
                        WHERE CD2.CITY_ID = C.ID
                        AND CD2.WEEK_END <= :week_end
                )
                LEFT JOIN CPE_TYPES CT ON CT.ID = CD.CPE_TYPE_ID
                WHERE C.TYPE = :city_type
            )
            SELECT
                CITY_ID,
                CITY_NAME,
                DISMANTLE_TYPE_ID,
                {", ".join(case_columns)},
                MAX(UPDATED_AT) AS max_updated_at
            FROM WEEKLY_DATA
            GROUP BY CITY_ID, CITY_NAME, DISMANTLE_TYPE_ID

            UNION ALL

            SELECT
                NULL AS city_id,
                'UKUPNO' AS city_name,
                DISMANTLE_TYPE_ID,
                {", ".join(sum_columns)},
                NULL AS max_updated_at
            FROM WEEKLY_DATA
            GROUP BY DISMANTLE_TYPE_ID

            ORDER BY DISMANTLE_TYPE_ID, CITY_ID NULLS LAST;
    """

    params = {"week_end": week_end, "city_type": city_type}

    result = db.session.execute(text(SQL_QUERY), params)
    return [row._asdict() for row in result.all()]


# --------AUTHORIZACIJA--------------------------------------------
# AUTHORIZATION ZA BILO KOJU AKCIJU: ONLY ADMIN
def admin_required():
    if current_user.is_authenticated and current_user.role == UserRole.ADMIN:
        return True
    flash("Niste Autorizovani!", "danger")
    return False


# AUTHORIZACIJA ZA CPECIFICNU AKCIJU: ADMIN OR USER AKO JE NJEGOV RESURS
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
        user_city_id == requested_city_id or current_user.role == UserRole.ADMIN
    ):
        return True
    flash("Niste Autorizovani!", "danger")
    return False


# AUTHORIZATION ZA VIEW:  ADMIN OR VIEW
def view_required():
    if current_user.is_authenticated and (
        current_user.role == UserRole.VIEW or current_user.role == UserRole.ADMIN
    ):
        return True
    flash("Niste Autorizovani!", "danger")
    return False


# -------------------------------- ROUTES----------------------------


# -------------HOME PAGE---------------------------
@app.route("/")
@login_required
def home():
    return render_template("home.html")


# ---------- ROUTES FOR PIVOT TABLE PAGES-----------------------


# A business week that runs from Saturday 00:00 → Friday 23:59
# vraca datum petka za svaku sedmicu
# If today is Monday (weekday=0): (4-0) % 7 = 4 → add 4 days → Friday
# If today is Friday (weekday=4): (4-4) % 7 = 0 → add 0 days → today (Friday)
# If today is Saturday (weekday=5): (4-5) % 7 = -1 % 7 = 6 → add 6 days → next Friday
def get_current_week_friday(today=None):
    today = today or date.today()
    # Friday = 4
    return today + timedelta(days=(4 - today.weekday()) % 7)


def get_passed_saturday(today=None):
    today = today or date.today()
    # Friday = 4
    return today - timedelta(days=(2+ today.weekday()) % 7)


# ----------PIVOT CPE-RECORDS-----------------
# PIVOTING IN SQL QUERY
@app.route("/cpe-records")
@login_required
def cpe_records():
    # to display today date on title
    today = date.today()
    print("today", today)

    # SATURDAY of this week
    # to mark row (red) if updated_at less than saturday
    saturday = get_passed_saturday()

    # date of friday in week
    current_week_end = get_current_week_friday()

    # list of all cpe_types object in db
    schema_list = get_cpe_types_column_schema()

    # 1. Build pivoted records from schema list but only for current week
    records = get_pivoted_cpe_inventory(schema_list, current_week_end)

    return render_template(
        "cpe_records.html",
        today=today.strftime("%d-%m-%Y"),
        saturday=saturday,
        current_week_end=current_week_end.strftime("%d-%m-%Y"),
        records=records,
        schema=schema_list,
    )


# UPDATE ROUTE FOR CPE-RECORDS TABLE, CALLED FROM INSIDE FORME INSIDE cpe-record
@app.route("/update_cpe", methods=["POST"])
@login_required
def update_recent_cpe_inventory():
    # 1. Extract and Convert Fields
    city_id_str = request.form.get("city_id")  # <-- GET THE HIDDEN ID
    city_name = request.form.get("city")

    if not city_id_str or not city_id_str.isdigit():
        flash("City ID is missing.", "danger")
        return redirect(url_for("home"))

    city_id = int(city_id_str)

    if not admin_and_user_required(city_id):
        return redirect(url_for("home"))

    current_week_end = get_current_week_friday()

    try:
        # Iterate through all submitted form items
        for key, value in request.form.items():
            # Keys are formatted as 'cpe-ID-NAME', e.g., 'cpe-1-IADS'
            # from .html form modal inputs
            if not key.startswith("cpe-"):
                continue
            _, cpe_type_id_str, _ = key.split("-", 2)  # Splits into ['cpe', 'ID']

            try:
                cpe_type_id = int(cpe_type_id_str)
            except ValueError:
                # Skip this record if ID or Quantity is invalid
                continue
            if value is None or value.strip() == "":
                quantity = 0
            else:
                quantity = int(value)

            if quantity < 0:
                flash("Količina ne može biti negativna.", "danger")
                return redirect(url_for("cpe_records"))

            # We insert a new record for every CPE type, FOR ONE CITY_ID
            db.session.execute(
                text("""
                    INSERT INTO cpe_inventory ( 
                                city_id,
                                cpe_type_id,
                                week_end,
                                quantity)
                    VALUES (:city_id,
                            :cpe_type_id,
                            :week_end,
                            :quantity)
                    ON CONFLICT (city_id, cpe_type_id, week_end)
                    DO UPDATE SET quantity = EXCLUDED.quantity, updated_at = NOW();
                    """),
                {
                    "city_id": city_id,
                    "cpe_type_id": cpe_type_id,
                    "week_end": current_week_end,
                    "quantity": quantity,
                },
            )

        db.session.commit()
        flash(f"Novo stanje za skladište {city_name} uspješno sačuvano!", "success")
    except Exception as e:
        db.session.rollback()
        print(f"Error during CpeInventory batch insert: {e}")
        flash("Došlo je do greške prilikom unosa u bazu.", "danger")

    # Redirect to Home (Post-Redirect-Get Pattern)
    # This prevents duplicate form submissions if the user hits refresh.
    return redirect(url_for("cpe_records"))


# PIVOTING IN SQL QUERY
@app.route("/cities/history/<int:id>")
@login_required
def city_history(id):
    # POSALJI ISTORIJSKU PAGINACIJU ZA TAJ GRAD
    city = Cities.query.get_or_404(id)

    if not admin_and_user_required(city.id):
        return redirect(url_for("home"))

    page = request.args.get("page", 1, int)
    per_page = 20

    # THIS IS LIST OF CPE TYPE OBJECTS, BUT ONLY ONE is_active
    schema_list = get_cpe_types_column_schema()

    # paginated_records is iterable SimplePagination object
    paginated_records = get_city_history_cpe_inventory(
        city_id=city.id, schema_list=schema_list, page=page, per_page=per_page
    )

    return render_template(
        "city_history.html",
        records=paginated_records,
        schema=schema_list,
        city=city,
    )


# ----------PIVOT CPE-DISMANTLE-RECORDS-----------------
# PIVOTING IN SQL QUERY
@app.route("/cpe-dismantle")
@login_required
def cpe_dismantle():
    # to display today date on title
    today = date.today()

    # SATURDAY of this week
    # to mark row (red) if updated_at less than saturday
    saturday = date.today() + timedelta(days=(5 - today.weekday()))

    # date of friday in week
    current_week_end = get_current_week_friday()

    # list of all cpe_types object in db but only if is_active_dismantle
    schema_list = get_cpe_types_column_schema("is_active_dismantle")

    # 1. Build pivoted records from schema list but only for current week_end
    records = get_pivoted_cpe_dismantle(
        schema_list, current_week_end, city_type=CityTypeEnum.IJ.value
    )
    # rows in records look like this:
    # {'city_id': 3, 'city_name': 'IJ Banja Luka', 'dismantle_type_id': 1, 'IADS': 148, 'VIP4205_VIP4302_1113': 345,..., 'max_updated_at': datetime.datetime(2025, 12, 26, 0, 0)}
    # {'city_id': 3, 'city_name': 'IJ Banja Luka', 'dismantle_type_id': 2, 'IADS': 148, 'VIP4205_VIP4302_1113': 345,..., 'max_updated_at': datetime.datetime(2025, 12, 26, 0, 0)}
    # {'city_id': 3, 'city_name': 'IJ Banja Luka', 'dismantle_type_id': 3, 'IADS': 148, 'VIP4205_VIP4302_1113': 345,..., 'max_updated_at': datetime.datetime(2025, 12, 26, 0, 0)}

    grouped_by_type = defaultdict(list)

    # grouped_by_type[1:[completed rows],2:[no remote rows],3:[no adapter rows],4:[no both rows]]
    for row in records:
        grouped_by_type[row["dismantle_type_id"]].append(row)

    # MORAJU SE SLAGATI SA ID KAKO SU DEFINISANI U POSTGRES TABELI dismantle_types
    COMPLETE_ID = 1
    NO_REMOTE_ID = 2
    NO_ADAPTER_ID = 3
    NO_BOTH_ID = 4

    ## row in complete only have objects that have iniside 'dismantle_type_id': 1
    complete_rows = grouped_by_type[COMPLETE_ID]

    # helper function for missing-grouping
    # We want missing_grouped to look like:
    """
    [
    {
        "city_name": "Sarajevo",
        "max_updated_at": ...,
        "IADS": {
            "remote": 1,
            "adapter": 2,
            "both": 0,
        },
        "HG8245": {
            "remote": 0,
            "adapter": 1,
            "both": 1,
        },
    },
    ...
    ]
    """
    missing_grouped = {}

    def ensure_city(city_id, city_name, updated_at):
        if city_id not in missing_grouped:
            missing_grouped[city_id] = {
                "city_id": city_id,
                "city_name": city_name,
                "max_updated_at": updated_at,
            }
            for item in schema_list:
                missing_grouped[city_id][item["name"]] = {
                    "remote": 0,
                    "adapter": 0,
                    "both": 0,
                }

    # Fill data for each dismantle type
    # row is from orginal sql query
    for row in grouped_by_type[NO_REMOTE_ID]:
        cid = row["city_id"]

        # ovim je filovan city_id, city_name and max_updated_at
        # ali su quantity nula
        ensure_city(cid, row["city_name"], row["max_updated_at"])

        # get the quantity
        for item in schema_list:
            missing_grouped[cid][item["name"]]["remote"] = row.get(item["name"], 0)

    for row in grouped_by_type[NO_ADAPTER_ID]:
        cid = row["city_id"]

        ensure_city(cid, row["city_name"], row["max_updated_at"])

        for item in schema_list:
            missing_grouped[cid][item["name"]]["adapter"] = row.get(item["name"], 0)

    for row in grouped_by_type[NO_BOTH_ID]:
        cid = row["city_id"]
        ensure_city(cid, row["city_name"], row["max_updated_at"])

        for item in schema_list:
            missing_grouped[cid][item["name"]]["both"] = row.get(item["name"], 0)

    # Convert to list for template
    missing_grouped = list(missing_grouped.values())

    return render_template(
        "cpe_dismantle_records.html",
        today=today.strftime("%d-%m-%Y"),
        saturday=saturday,
        current_week_end=current_week_end.strftime("%d-%m-%Y"),
        schema=schema_list,
        complete=complete_rows,
        missing=missing_grouped,
    )


# ----------PIVOT STB-RECORDS-----------------
# PIVOTING IN FLASK
@app.route("/stb-records")
@login_required
def stb_records():
    SQL_QUERY = """
            WITH
            LAST_WEEK AS (
                SELECT DISTINCT
                    WEEK_END
                FROM
                    STB_INVENTORY
                ORDER BY
                    WEEK_END DESC
                LIMIT
                    4
            )
            SELECT
                T.ID,
                T.LABEL,
                I.WEEK_END,
                I.QUANTITY
            FROM
                STB_TYPES T
                LEFT JOIN STB_INVENTORY I 
                    ON I.STB_TYPE_ID = T.ID
                    AND I.WEEK_END IN (SELECT WEEK_END FROM LAST_WEEK)
            WHERE t.is_active = true
            ORDER BY i.week_end DESC;
    """
    # returns all rows as a list of tuples
    #  ('STB-100', '2025-11-25', 90),
    rows = db.session.execute(text(SQL_QUERY)).fetchall()

    # get time when table stb_inventory lates updated
    last_updated = db.session.execute(
        text("""SELECT
        MAX(updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Sarajevo')
        FROM stb_inventory;""")
    ).scalar()

    # Creates a dictionary of dictionary
    # dictionary of lambda funkcija
    # lambda prima 1 vrijednost vraca objekat
    # "name" is name of STB, data is {date1:quantity1, date2:quantity2,...}
    table = defaultdict(lambda: {"name": None, "data": defaultdict(int)})

    # Collects all unique weeks from the query, so we know which columns to display.
    weeks = set()

    # Transforming rows into a pivot-friendly structure
    for r in rows:
        table[r.id]["name"] = r.label
        quantity = r.quantity or 0
        # Check if week_end actually exists before adding it to the se
        if r.week_end is not None:
            table[r.id]["data"][r.week_end] += quantity
            weeks.add(r.week_end)

    # table is in format:
    # table = {1: {"name": "STB-100","data": {date(2025,12,27): 90,date(2025,12,20): 80}},
    #          2: {"name": "STB-200","data": {date(2025,12,27): 10,date(2025,12,20): 80}},
    #           ....
    # }}

    # Sorts weeks ascending (latest week last)
    weeks = sorted(weeks)

    # calculate current week week_end date
    current_week_end = get_current_week_friday()

    # Calculate totals quantityes per week
    # table.values() → each STB
    # t["data"] → dict {week → quantity}
    # .get(week, 0) → safe for missing weeks
    totals = {
        week: sum(t["data"].get(week, 0) for t in table.values()) for week in weeks
    }
    # totals is a dictionary like:
    # {'2025-11-25': 210, '2025-11-18': 95, '2025-11-11': 0, '2025-11-04': 0}
    # totals: {datetime.date(2025, 12, 27): 3721, datetime.date(2025, 12, 20),.....}:

    return render_template(
        "stb_records.html",
        weeks=weeks,
        current_week_end=current_week_end,
        table=table,
        totals=totals,
        last_updated=last_updated,
    )


@app.route("/update_stb", methods=["POST"])
@login_required
def update_recent_stb_inventory():
    current_week_end = get_current_week_friday()
    try:
        for key, value in request.form.items():
            if not key.startswith("qty_"):
                continue
            try:
                # key je tima qty_1, qty_2,....
                stb_type_id = int(key.split("_", 1)[1])

                quantity = int(value or 0)

            except ValueError:
                # Skip this record if ID or Quantity is invalid
                continue

            # because of UNIQUE (stb_type_id, week_end) constraints
            # added when defining table StbInventory in postgres
            # business logic is: “For this week, insert if missing, update if exists”
            # That is exactly what PostgreSQL ON CONFLICT DO UPDATE is for.
            # ORM add_all() cannot do UPSERT cleanly
            db.session.execute(
                text("""
                    INSERT INTO stb_inventory (stb_type_id, week_end, quantity)
                    VALUES (:stb_id, :week_end, :quantity)
                    ON CONFLICT (stb_type_id, week_end)
                    DO UPDATE SET quantity = EXCLUDED.quantity, updated_at = NOW();
                """),
                {
                    "stb_id": stb_type_id,
                    "week_end": current_week_end,
                    "quantity": quantity,
                },
            )

        # PostgreSQL loves batching UPSERTs in a single transaction.
        # UPSERT = “UPDATE or INSERT”.
        # Only on commit() does SQLAlchemy:
        # Send all pending SQL statements to the database
        # Wrap them in a transaction
        # `Make them permanent in the DB
        db.session.commit()
        flash(
            f"Novo stanje za {current_week_end} uspješno sačuvano!",
            "success",
        )
    except Exception as e:
        db.session.rollback()
        print(e)
        flash("Greška prilikom čuvanja podataka.", "danger")

    # Redirect to Home (Post-Redirect-Get Pattern)
    # This prevents duplicate form submissions if the user hits refresh.
    return redirect(url_for("stb_records"))


# ----------PIVOT ONT-RECORDS-----------------
# return date of last day of current month
def get_current_month_end(today=None):
    # Take today
    today = today or date.today()

    # Move to first day of next month
    if today.month == 12:
        first_next_month = date(today.year + 1, 1, 1)
    else:
        # Jump to the first day of the next month
        first_next_month = date(today.year, today.month + 1, 1)

    # Subtract one day Step back one day → last day of current month
    return first_next_month - timedelta(days=1)


# PIVOTING IN FLASK
@app.route("/ont-records")
@login_required
def ont_records():
    SQL_QUERY = """
            WITH
            LAST_MONTH AS (
                SELECT DISTINCT
                    MONTH_END
                FROM
                    ONT_INVENTORY
                ORDER BY
                    MONTH_END DESC
                LIMIT
                    4
            )
            SELECT
                c.id, 
                c.name, 
                i.month_end, 
                i.quantity 
            FROM
                CITIES C
                LEFT JOIN ONT_INVENTORY I 
                    ON I.CITY_ID = C.ID
                    AND I.MONTH_END IN (SELECT MONTH_END FROM LAST_MONTH)
            WHERE C.TYPE = 'IJ'
            ORDER BY  C.ID, i.month_end DESC ;
    """

    rows = db.session.execute(text(SQL_QUERY)).fetchall()

    # get time when table ont_inventory lates updated
    last_updated = db.session.execute(
        text("""SELECT
        MAX(updated_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Sarajevo')
        FROM ont_inventory;""")
    ).scalar()

    # The statement creates a dictionary of dictionaries
    # defaultdict(default_factory)
    # default_factory: This is a function (or constructor) that provides
    #  the default value for the key.
    # The innermost defaultdict(int) uses int as its default factory.
    # The function: lambda: (takes no arguments) returns defaultdict(int).
    table = defaultdict(lambda: {"name": None, "data": defaultdict(int)})

    months = set()

    # Transforming rows into a pivot-friendly structure
    for r in rows:
        table[r.id]["name"] = r.name
        quantity = r.quantity or 0
        if r.month_end is not None:
            table[r.id]["data"][r.month_end] += quantity
            months.add(r.month_end)

    # table is in format:
    # table = {1: {"name": "STB-100","data": {date(2025,12,27): 90,date(2025,12,20): 80}},
    #          2: {"name": "STB-200","data": {date(2025,12,27): 10,date(2025,12,20): 80}},
    #           ....}}

    # sortija od najveceg do najmanjeg i odaberi samo prvo 4 recorda
    months = sorted(months)

    # calculate current week week_end date
    current_month_end = get_current_month_end()

    # calculate tottal SABERI KVANTITETE PO MIJESECIMA
    totals = {
        month: sum(t["data"].get(month, 0) for t in table.values()) for month in months
    }

    return render_template(
        "ont_records.html",
        months=months,
        current_month_end=current_month_end,
        table=table,
        totals=totals,
        last_updated=last_updated,
    )


@app.route("/update_ont", methods=["POST"])
@login_required
def update_recent_ont_inventory():
    current_month_end = get_current_month_end()
    try:
        for key, value in request.form.items():
            if not key.startswith("qty_"):
                continue
            try:
                # key je tima qty_1, qty_2,....
                city_id = int(key.split("_", 1)[1])
                quantity = int(value or 0)
            except ValueError:
                # Skip this record if ID or Quantity is invalid
                continue

            db.session.execute(
                text("""

            INSERT INTO ont_inventory (city_id, month_end, quantity)
                    VALUES (:city_id, :month_end, :quantity)
                    ON CONFLICT (city_id, month_end)
                    DO UPDATE SET quantity = EXCLUDED.quantity, updated_at = NOW();
            """),
                {
                    "city_id": city_id,
                    "month_end": current_month_end,
                    "quantity": quantity,
                },
            )

        # PostgreSQL loves batching UPSERTs in a single transaction.
        # UPSERT = “UPDATE or INSERT”.
        # Only on commit() does SQLAlchemy:
        # Send all pending SQL statements to the database
        # Wrap them in a transaction
        # `Make them permanent in the DB
        db.session.commit()
        flash(
            f"Novo stanje za {current_month_end} uspješno sačuvano!",
            "success",
        )

    except Exception as e:
        db.session.rollback()
        print(e)
        flash("Greška prilikom čuvanja podataka.", "danger")

    return redirect(url_for("ont_records"))


# ----------AUTHENTICATED AND AUTHORIZED PAGES---------------------


# ----------------ADMIN DASHBOARD PAGE-----------
@app.route("/admin/")
@login_required
def admin_dashboard():
    return render_template("admin.html")


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


@app.route("/admin/cpe_inventory/add", methods=["POST"])
@login_required
def admin_add_to_cpe_inventory():
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


# -------------CPE_DISMANTLE CRUD----------------------------------------
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


# -------------STB_INVENTORY CRUD----------------------------------------
@app.route("/admin/stb_inventory")
@login_required
def admin_stb_inventory():
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


# -------------ONT_INVENTORY CRUD----------------------------------------
@app.route("/admin/ont_inventory")
@login_required
def admin_ont_inventory():
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
        type_string = request.form.get("type")
        print("type_string ", type_string)

        # 1. Validation: Convert string to Enum object safely
        try:
            selected_type = CityTypeEnum(type_string)
        except ValueError:
            flash("Izabrani tip nije važeći.", "danger")
            return redirect(url_for("admin_add_city"))

        # Validation: name must be unique
        existing_city = Cities.query.filter_by(name=name).first()
        if existing_city:
            flash("Skladište već postoji", "danger")
            return redirect(url_for("admin_add_city"))

        print("type", type)
        db.session.add(Cities(name=name, type=selected_type))
        db.session.commit()
        return redirect(url_for("admin_cities"))

    types = [t.value for t in CityTypeEnum]
    print("types", types)
    # THIS IS FOR GET REQUEST WHEN OPENING ADD FORM
    return render_template("admin/cities_add.html", types=types)


@app.route("/admin/cities/edit/<int:id>", methods=["GET", "POST"])
@login_required
def admin_edit_city(id):
    if not admin_required():
        return redirect(url_for("admin_cities"))

    city = Cities.query.get_or_404(id)

    if request.method == "POST":
        name = request.form.get("name")
        type_string = request.form.get("type")

        # 1. Validation: Convert string to Enum object safely
        try:
            selected_type = CityTypeEnum(type_string)
        except ValueError:
            flash("Izabrani tip nije važeći.", "danger")
            return redirect(url_for("admin_edit_city", id=id))

        # name uniqueness (except current name)
        existing_city = Cities.query.filter(
            Cities.name == name, Cities.id != id
        ).first()
        if existing_city:
            flash("Skladiste već postoji!", "danger")
            return redirect(url_for("admin_edit_city", id=id))

        city.name = name
        city.type = selected_type

        try:
            db.session.commit()
            flash("Skladiste uspješno izmijenjeno!", "success")
            return redirect(url_for("admin_cities", id=id))
        except Exception as e:
            db.session.rollback()
            flash(f"Greška prilikom izmjene: {e}", "danger")
            return redirect(url_for("admin_edit_city", id=id))

    types = [t.value for t in CityTypeEnum]

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


@app.route("/admin/users/edit/<int:id>", methods=["GET", "POST"])
@login_required
def admin_edit_user(id):
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


@app.route("/admin/users/delete/<int:id>")
@login_required
def admin_delete_user(id):
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


@app.route("/admin/cpe_types/edit/<int:id>", methods=["GET", "POST"])
@login_required
def admin_edit_cpe_type(id):
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
        cpe.is_active_total = (
            "is_active_total" in request.form
        )  # THIS IS THE CORRECT WAY
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


# -------------STB_TYPES CRUD----------------------------------------
@app.route("/admin/stb_types")
@login_required
def admin_stb_types():
    if not view_required():
        # return "Forbidden", 403
        return redirect(url_for("admin_dashboard"))
    stbs = StbTypes.query.order_by(StbTypes.id).all()
    return render_template("admin/stb_types.html", stbs=stbs)


@app.route("/admin/stb_types/add", methods=["GET", "POST"])
@login_required
def admin_add_stb_type():
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


@app.route("/admin/stb_types/edit/<int:id>", methods=["GET", "POST"])
@login_required
def admin_edit_stb_type(id):
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


# -----------------DISMANTLE TYPES CRUD---------------------
@app.route("/admin/dismantle_status")
@login_required
def admin_dismantle_status():
    if not view_required():
        # return "Forbidden", 403
        return redirect(url_for("admin_dashboard"))
    status = DismantleTypes.query.order_by(DismantleTypes.id).all()
    return render_template("admin/dismantle_types.html", status=status)


@app.route("/admin/dismantle_status/add", methods=["GET", "POST"])
@app.route("/admin/dismantle_status/add")
@login_required
def admin_add_dismantle_status():
    if not admin_required():
        return redirect(url_for("admin_dismantle_status"))

    # THIS IS FOR SUMBITING REQUEST
    if request.method == "POST":
        label = request.form.get("label")
        description = request.form.get("description")

        # Validation: LABEL must be unique
        existing_label = DismantleTypes.query.filter_by(label=label).first()
        if existing_label:
            flash("Labela već postoji", "danger")
            return redirect(url_for("admin_add_dismantle_status"))

        db.session.add(DismantleTypes(label=label, description=description))
        db.session.commit()
        return redirect(url_for("admin_dismantle_status"))

    # THIS IS FOR GET REQUEST WHEN INICIALY OPENING ADD FORM
    return render_template(
        "admin/dismantle_types_add.html",
    )


@app.route("/admin/dismantle_status/edit/<int:id>", methods=["GET", "POST"])
@login_required
def admin_edit_dismantle_status(id):
    if not admin_required():
        return redirect(url_for("admin_dismantle_status"))

    dismantle = DismantleTypes.query.get_or_404(id)

    if request.method == "POST":
        label = request.form.get("label")
        description = request.form.get("description")

        # Validation: LABEL must be unique
        existing_label = DismantleTypes.query.filter(
            DismantleTypes.label == label, DismantleTypes.id != id
        ).first()
        if existing_label:
            flash("Labela već postoji", "danger")
            return redirect(url_for("admin_dismantle_status"))

        dismantle.id = id
        dismantle.label = label
        dismantle.description = description

        try:
            db.session.commit()
            flash("Tip demontaže uspješno izmijenjen!", "success")
            return redirect(url_for("admin_dismantle_status"))
        except Exception as e:
            db.session.rollback()
            flash(f"Greška prilikom izmjene tipa demontaže: {e}", "danger")
            return redirect(url_for("admin_edit_dismantle_status", id=id))

    return render_template("admin/dismantle_types_edit.html", dismantle=dismantle)


# -----------------LOGIN AUTENTIFIKACIJA------------------------
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


# --------------- LOGGOUT-----------------------
@app.route("/logout")
@login_required
def logout():
    username_to_flash = current_user.username
    logout_user()
    flash(f"Doviđenja, {username_to_flash}", "success")
    return redirect(url_for("login"))


# -----MAIN LOOP-----------
# Only needed for local development
# python app.py
# During production, your Dockerfile runs Gunicorn instead,
# so that block never executes.
if __name__ == "__main__":
    app.run(debug=True)  # <-- This enables the reloader and debugger
