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


# SOURCE OF TRUTH FOR WHOLE CPE-RECORDS TABLE
# THIS IS LIST OF FULL CPETYPE OBJECTS, BUT ONLY  is_active
# FROM THIS SCHEMA LIST:
# 1. WE USE IT TO BUILD RAW DYNAMIC SQL QUERY
# 2. WE ALSO USE IT IN HTML TABLES TEMPLATES AND IN ROUTES
def get_cpe_column_schema():
    # 2. Get full data (id, name, label, type) from Cpe_Types table
    cpe_types = (
        db.session.query(CpeTypes.id, CpeTypes.name, CpeTypes.label, CpeTypes.type)
        .filter(CpeTypes.is_active)
        .order_by(CpeTypes.id)
        .all()
    )

    # Prepare the structured list and separate lists
    schema_list = [
        {"id": id, "name": name, "label": label, "type": type}
        for id, name, label, type in cpe_types
    ]

    return schema_list


# This approach bypasses the ORM's object mapping for this specific complex query,
# treating it purely as a data fetch, which is necessary when using custom database
# functions like crosstab.
def get_pivoted_data(schema_list: list):
    if not schema_list:
        # Return empty data lists immediately if no active CPE types are found
        return []

    # Extract ONLY the model names (the first element in the tuple)
    # This is what CROSSTAB uses for column names
    model_names = [item["name"] for item in schema_list]

    # for first select
    # Create the comma-separated list of model names (for the final SELECT)
    # e.g., 'p."H267N", p."Arris VIP4205/VIP4302/1113", ...'
    selected_columns = ", ".join([f'p."{name}"' for name in model_names])

    # for pivot table as
    # Create the comma-separated list of quoted model names (for the SQL)
    # e.g., '"H267N" int, "Arris VIP4205/VIP4302/1113" int, ...'
    quoted_columns = ", ".join([f'"{name}" int' for name in model_names])

    # for sum columns
    # To ensure your "UKUPNO" (Total) row always shows a number, use COALESCE
    sum_columns = ", ".join(
        [f'COALESCE(SUM("{name}"),0) AS "{name}"' for name in model_names]
    )

    # raw SQL statement, as crosstab isn't a standard, ORM-mappable function
    # Inject these lists into the complete SQL template
    SQL_QUERY = f"""
    WITH latest_pivot AS (
        SELECT
            C.NAME AS CITY_NAME, -- Add CITY_NAME here for final result
            P.CITY_ID, -- For ordering purposes
            {selected_columns}, -- COMMA separated list of columns
            MAX_TS.MAX_UPDATED_AT
        FROM
            (
                SELECT
                    *
                FROM
                    CROSSTAB (
                        $QUERY$
                        SELECT
                            R.CITY_ID,
                            S.NAME AS CPE_MODEL,
                            R.QUANTITY
                        FROM
                            (
                                SELECT
                                    CITY_ID,
                                    CPE_TYPE_ID,
                                    QUANTITY,
                                    UPDATED_AT,
                                    ROW_NUMBER() OVER (
                                        PARTITION BY CITY_ID, CPE_TYPE_ID
                                        ORDER BY UPDATED_AT DESC
                                    ) AS RN
                                FROM CPE_INVENTORY
                            ) AS R
                            JOIN CPE_TYPES S ON R.CPE_TYPE_ID = S.ID
                        WHERE RN = 1
                        ORDER BY R.CITY_ID
                        $QUERY$,
                        $CATEGORY$
                        SELECT NAME FROM CPE_TYPES WHERE NAME IN ({", ".join([f"'{name}'" for name in model_names])}) ORDER BY ID
                        $CATEGORY$
                    ) AS PIVOT_TABLE (
                        CITY_ID INTEGER,
                        {quoted_columns}
                    )
            ) AS P
            JOIN CITIES C ON C.ID = P.CITY_ID
            LEFT JOIN (
                SELECT
                    CITY_ID,
                    MAX(UPDATED_AT) AS MAX_UPDATED_AT
                FROM
                    CPE_INVENTORY
                GROUP BY
                    CITY_ID
            ) AS MAX_TS ON MAX_TS.CITY_ID = P.CITY_ID
        )
    
    -- Data Rows
    SELECT 
        CITY_ID, 
        CITY_NAME, 
        {selected_columns.replace("p.", "")}, -- Remove 'p.' alias as we are selecting directly from latest_pivot
        MAX_UPDATED_AT
    FROM latest_pivot

    UNION ALL

    -- Total Row
    SELECT 
        NULL::INTEGER AS CITY_ID,
        'UKUPNO'::VARCHAR AS CITY_NAME,
        {sum_columns},
        NULL::TIMESTAMP AS MAX_UPDATED_AT
    FROM latest_pivot 
    
    ORDER BY 
        CITY_ID ASC NULLS LAST; 
    """

    # 1. Prepare the raw SQL string
    # 2. Execute the query
    result = db.session.execute(text(SQL_QUERY))

    # 3. Fetch all rows
    # The result is a ResultProxy; .mappings() helps convert rows to dicts
    # for easier handling in a web app.
    pivoted_data = [row._asdict() for row in result.all()]

    return pivoted_data


# The main difference with get_pivoted_data is that, for the history,
# you need to pivot on the updated_at timestamp
# and the cpe_model, while filtering for a single city_id
def get_city_history_pivot(city_id: int, schema_list: list, page: int, per_page: int):
    """
    Retrieves the historical records for a specific city_id, pivoted by CPE type.
    This query handles pagination internally based on the unique UPDATED_AT timestamp.
    """
    if not schema_list:
        # Return empty data lists immediately if no active CPE types are found
        return []

    model_names = [item["name"] for item in schema_list]

    quoted_columns = ", ".join([f'"{name}" INT' for name in model_names])
    selected_columns = ", ".join([f'P."{name}"' for name in model_names])

    # koloko ima rows za izabrani grad
    # We need a separate query to get the total count for pagination
    count_query = text(
        f"""SELECT 
                COUNT(DISTINCT UPDATED_AT) 
            FROM CPE_INVENTORY 
            WHERE CITY_ID={city_id}"""
    )

    total_count = db.session.execute(count_query).scalar()

    # Calculate offset
    offset = (page - 1) * per_page

    # THIS IS THE QUERY FOR CROSSTAB FUNCTION
    # IT WILL FIND ALL PIVOTED DATAD (ROWS) FOR SELECTED CITY_ID
    inner_crosstab_query = f"""
    SELECT
        R.UPDATED_AT,
        S.NAME AS CPE_MODEL,
        R.QUANTITY
    FROM 
        CPE_INVENTORY R
    JOIN 
        CPE_TYPES S ON R.CPE_TYPE_ID=S.ID
    WHERE
        R.CITY_ID={city_id}
    ORDER BY
        R.UPDATED_AT DESC, S.NAME
    """

    # CRITICAL: We need to figure out which OF UPDATED_AT timestamps belong to the current page.
    # We do this using a subquery (distinct_updates) to find only the timestamps that are inside offset/limit.

    # 1.WE FIND ALL THE PIVOTED DATA IN CROSSTAB
    # 2. AND THEN JOIN WITH distinct_updates TABLE
    # distinct_updates TABLE ACT AS A FILTER.
    # IT HOLDS UPDATE_AT RECORDA LIMITED BY PAGE AN OFFSET
    # SO OUR FINAL PIVOTED DATA IS PAGINATED THROUGH FILTERING
    # PAGINATION ON ALL PIVOTED DATA IS NOT PERFORMANT
    SQL_QUERY = f"""
    WITH distinct_updates AS (
        SELECT DISTINCT UPDATED_AT
        FROM CPE_INVENTORY
        WHERE CITY_ID = {city_id}
        ORDER BY UPDATED_AT DESC
        LIMIT {per_page} OFFSET {offset}
    )
    SELECT
        D.UPDATED_AT,
        {selected_columns}
    FROM
        CROSSTAB (
            $QUERY$
            {inner_crosstab_query}
            $QUERY$,
            $CATEGORY$
            SELECT NAME FROM CPE_TYPES WHERE NAME IN ({", ".join([f"'{name}'" for name in model_names])}) ORDER BY ID
            $CATEGORY$
        ) AS P (
            UPDATED_AT TIMESTAMP,
            {quoted_columns}
        ) 
    JOIN
        distinct_updates D ON D.UPDATED_AT = P.UPDATED_AT
    ORDER BY
        P.UPDATED_AT DESC;
    """
    # The CROSSTAB generates a large pivoted table (P) containing all historical records for the city
    #  (row ID = UPDATED_AT).
    # The JOIN acts as a filter. It discards all rows from the massive
    # pivoted table (P) except for those whose UPDATED_AT timestamp matches one of the
    # handful of timestamps found in the small, already-paginated distinct_updates list (D).

    result = db.session.execute(text(SQL_QUERY))

    # pivoted_data is now list
    pivoted_data = [row._asdict() for row in result.all()]

    # paginate is iterable SimplePagination object
    paginate = SimplePagination(
        page=page, per_page=per_page, total=total_count, items=pivoted_data
    )

    return paginate


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


# -------------HOME PAGE NEW---------------------------
@app.route("/")
@login_required
def home():
    return render_template("home.html")


# ----------AUTENTHENTICATED ROUTES FOR USE PAGES-----------------------


# ----------PIVOT CPE-RECORDS-----------------
@app.route("/cpe-records")
@login_required
def cpe_records():
    today = date.today()
    # today.weekday() gives 0 for Monday, 6 for Sunday
    # Subtracting gives the date for this week's Monday
    monday = today - timedelta(days=today.weekday())  # Monday of this week

    schema_list = get_cpe_column_schema()

    # 1. Build pivoted records from schema list
    records = get_pivoted_data(schema_list)
    return render_template(
        "cpe_records.html",
        today=today.strftime("%d-%m-%Y"),
        monday=monday,
        records=records,
        schema=schema_list,
    )


# UPDATE CPE-RECORDS TABLE, CALLED FROM INSIDE UPDATE FORME
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

    current_time = datetime.now()
    records_to_add = []

    # Iterate through all submitted form items
    for key, value in request.form.items():
        # Keys are formatted as 'cpe-ID-NAME', e.g., 'cpe-1-IADS'
        # from .html form modal inputs
        if key.startswith("cpe-"):
            parts = key.split("-", 2)  # Splits into ['cpe', 'ID', 'NAME']
            if len(parts) == 3:
                cpe_type_id_str = parts[1]  #'DOBAVI ID'
                try:
                    cpe_type_id = int(cpe_type_id_str)
                    quantity = int(value or 0)
                except ValueError:
                    # Skip this record if ID or Quantity is invalid
                    continue

                # We insert a new record for every CPE type, FOR ONE CITY_ID
                new_record = CpeInventory(
                    city_id=city_id,
                    cpe_type_id=cpe_type_id,
                    quantity=quantity,
                    updated_at=current_time,
                )
                # gather all record from one row OF one city
                records_to_add.append(new_record)

    # 4. Execute Single Batch Transaction
    if records_to_add:
        try:
            db.session.add_all(records_to_add)
            db.session.commit()
            flash(f"Novo stanje za skladište {city_name} uspješno sačuvano!", "success")
        except Exception as e:
            db.session.rollback()
            print(f"Error during CpeInventory batch insert: {e}")
            flash("Došlo je do greške prilikom unosa u bazu.", "danger")
    else:
        flash("Nije pronađen nijedan CPE za unos.", "warning")

    # Redirect to Home (Post-Redirect-Get Pattern)
    # This prevents duplicate form submissions if the user hits refresh.
    return redirect(url_for("cpe_records"))


@app.route("/cities/history/<int:id>")
@login_required
def city_history(id):
    # POSALJI ISTORIJSKU PAGINACIJU ZA TAJ GRAD
    city = Cities.query.get_or_404(id)

    if not admin_and_user_required(city.id):
        return redirect(url_for("home"))

    page = request.args.get("page", 1, int)
    per_page = 20

    # THIS IS LIST OF CPETYPE OBJECTS, BUT ONLY ONE is_active
    schema_list = get_cpe_column_schema()

    # paginated_records is iterable SimplePagination object
    paginated_records = get_city_history_pivot(
        city_id=city.id, schema_list=schema_list, page=page, per_page=per_page
    )

    return render_template(
        "city_history.html",
        records=paginated_records,
        schema=schema_list,
        city=city,
    )


# ----------PIVOT CPE-DISMANTLE-RECORDS-----------------


@app.route("/cpe-dismantle")
@login_required
def cpe_dismantle():
    return render_template("cpe_dismantle.html")


# ----------PIVOT STB-RECORDS-----------------


# vraca datum petka za svaku sedmicu
# posto je petak datum u svakoj koloni
def get_current_week_end(today=None):
    today = today or date.today()
    # Friday = 4 (Mon=0)
    return today + timedelta(days=(4 - today.weekday()) % 7)


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
    current_week_end = get_current_week_end()

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
    current_week_end = get_current_week_end()
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


# ----------AUTTORHIZED PAGES---------------------


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
    cities = Cities.query.order_by(Cities.id).all()
    # cities = db.session.query(CpeInventory.city_id).distinct().all()

    # Mora biti CpeTypes jer dodajemo novi element u CPEInventory
    cpe_types = CpeTypes.query.filter_by(is_active=True).order_by(CpeTypes.id).all()

    return render_template(
        "admin/cpe_inventory.html",
        records=pagination.items,
        pagination=pagination,
        sort_by=sort_by,
        direction=direction,
        cities=cities,
        cpe_types=cpe_types,
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


# ------------POMOCNE LISTE------------
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
        cpe.is_active = "is_active" in request.form  # THIS IS THE CORRECT WAY

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


# -------------STB TYPES CRUD----------------------------------------
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
