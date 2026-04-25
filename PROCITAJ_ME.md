# FOR GIT BASH:

# --CREATE NEW PEOJECT---

# python -m venv .venv

# ----ACIVATE ENVIROMENT-----

# source .venv/Scripts/activate

# --INSTA PACKETS----

# Install: python -m pip install <package-name>

# pip install Flask

# pip install -U Flask-SQLAlchemy -ORM LAYER

# pip install psycopg2-binary - POSTGRE DRIVER

# -------RUN LOCAL DEVELOPENT APP USING GIT BASH------------

# set DB_HOST=localhost

THIS RUN POSTGRES AND PGADMIN ON LOCAL DOCKER

# docker compose -f docker-compose.dev.yml up -d

# dockerizuje only postgres and pgadmin

```bash
docker compose -f docker-compose.dev.yml up -d
```

THIS RUN FLASK APP LOCALO ON PC

# python app.py

# localhost:5000 (Flask)

# - POSTGRES DB IS RUNNING ON ----

# localhost:5432 (DB)

# -------PG ADMIN-----------

# Go to: http://localhost:5050

# Login with your pgAdmin credentials.

# Connect to your PostgreSQL server

# Right-click Servers → Register → Server

# --------------------------------------------------------------------------------------------------

# problem with pip in windows AND HOLOW VENV

Activate: source .venv/Scripts/activate

# Install: python -m pip install <package-name>

python -m pip install -r requirements.txt

Update Requirements: It is best practice to immediately update your file so your project stays reproducible:

Bash
python -m pip freeze > requirements.txt

Why avoid just pip install?
On Windows, pip is often an independent .exe file. Sometimes, your terminal might activate the virtual environment's Python, but the pip command remains "stuck" pointing to your Global Python.

By using python -m pip, you are explicitly telling the system: "Use the Python interpreter I'm currently using to run its own internal version of pip." This guarantees the package lands in your .venv folder.

# Deactivate first

```bash
deactivate
```

# Re-activate using the full path

```bash
source ./.venv/Scripts/activate
```

Now, run this specific command to check:

```bash
python -c "import sys; print(sys.executable)"
```

If this still shows C:/Users/zoran.dasic/..., then your virtual environment is essentially "hollow."

Delete the broken venv folder (physically delete the .venv folder in your project).

Create a new one using the full path to your global Python:

```bash
/c/Users/zoran.dasic/AppData/Local/Programs/Python/Python313/python -m venv .venv
```

Activate it:

```bash
source .venv/Scripts/activate
```

Re-install your requirements:

```bash
python -m pip install -r requirements.txt
```

# -----------------------------------------------------------------------------------------------------------

```
Host: db (if using Docker compose) or localhost (if local install)

Port: 5432

Username: postgres

Password: mypassword

Database: mydb (the one you used in Flask)
```

```bash
TABELE UNUTAR PGADMINA
Servers
 └─ Local Postgres
      └─ Databases
           └─ mydb
                └─ Schemas
                     └─ public
                          └─ Tables
```

# Right-click users → View/Edit Data → All Rows

# ---------------------IN LOCAL PRODUCTION ---------------

# docker compose -f docker-compose.prod.localy.yml up -d --build

# docker compose -f docker-compose.prod.localy.yml build --no-cache

# dockerizuje flask, postgres and pgadmin

```bash
docker compose -f docker-compose.prod.localy.yml up -d
docker compose -f docker-compose.prod.localy.yml up -d --build
```

# -----------------------IN REMOTE PRODUCTION----------

# EXPORT DOCKER IMAGES:

# docker save -o ~/Desktop/cpe-analiza-flask.tar cpe-analiza-flask:latest

# scp "docker-compose.prod.yml" root@10.198.3.92:5000:/

# scp "cpe-sip-nextjs-app.tar" root@10.198.3.92:5000:/

# NA SERVERU

```bash
docker compose -f docker-compose.prod.yml up -d
```

# --------entrypoint.sh----------------------

entrypoint.sh JE BASH SCRIT KOJI SE KORISTI U PRODUKCIJISKOJ
VERZIJI DOCKER COMPOSA.

IT IS REFERNCED INSIDE Dockerfile:

# Set the Entrypoint to run your script first

ENTRYPOINT ["entrypoint.sh"]

The ENTRYPOINT defined in your Dockerfile specifies the program that runs when a container starts. Think of it as the main executable for your container.

In summary, the sequence will be:

docker compose up is run.

The flask container starts.

The entrypoint.sh script executes.

The script waits for the database (db).

The script runs flask create-admin.

First time: The user is created and committed to the persistent pgdata volume.

Subsequent times: The script checks the persistent data, finds the user, and skips the insertion.

The script runs exec gunicorn..., which starts the main Flask application.

# --------------RESTART DOCKER AND DOCKER NETWORKS----------------

# docker compose -f docker-compose.dev.yml down -v

# docker network ls

# Remove all stale / unused networks:

# docker network prune -f

# docker ps -a

# Bring up Compose stack from scratch:

# docker compose -f docker-compose.dev.yml up -d --force-recreate

# ------------create table in pgadmin with sql----------------------

# Click once on mydb so it becomes highlighted (this selects the database)

# At the top menu click Tools → Query Tool

# --------------------RESTART DOCKER DEAMON NA SERVER-----------------------

```bash
# Stop Docker
sudo systemctl stop docker

# Remove stale Docker network metadata
# This clears all stored network metadata. Docker will recreate it on startup.
sudo rm -f /var/lib/docker/network/files/local-kv.db

# Remove all unused networks just in case
docker network prune -f

# Start Docker daemon
sudo systemctl start docker

# Bring up your Compose stack cleanly, recreating containers and networks
docker compose -f /path/to/docker-compose.dev.yml up -d --force-recreate
```

#n modern cloud environments images are stripped down to be as small as possible.
#Tools like ping, telnet, nc (netcat), or curl are often not installed for security and size reasons.
#However, Bash is almost always available. This provides a "native" way to

# check connectivity on linux without installing extra packages.

#bash -c "..."This runs a new instance of the Bash shell
#/dev/tcp/host/port: This is not a real file on the disk. It is a Bash built-in feature (a pseudo-device).
#When you redirect input or output to this path, Bash attempts to open a TCP socket to the specified host and port.
#The command following it (echo 'FAILED') runs only if the previous command sequence failed

```sh
bash -c "echo > /dev/tcp/db/5432 && echo 'OK' || echo 'FAILED'"

```

# ------------------------------------------------------------

# CREATE MODEL FROM POSTGRES TABLES:

# --------------------------------------------------------

```bash
sqlacodegen postgresql://postgres:mypassword@localhost:5431/mydb > models.py
```

INSIDE models.py:

```python
from flask_login import UserMixin

db = SQLAlchemy()

#REPLACE Base with db.Model


# UserMixin automatically provides:
# is_authenticated
# is_active
# is_anonymous
# get_id()
# Exactly what Flask-Login needs.
class Users(db.Model, UserMixin):

```

# --------------------------------------

# CREATE ADMIN USER VIA FLASK CLI SCRIPT:

# --------------------------------------------------------

1. CREATE CLI FLASK SCRIPT TO create_admin_cli.py

```python
@click.command("create-admin")  # Define the command name
@with_appcontext
def create_initial_admin(username="admin", plain_password="admin123"):
```

2. THEN IMPORT INISIDE app.py TO REGISTER COMMAND

# Flask will now register the 'create-admin' command

```python
from create_admin_cli import create_initial_admin_comman

app.cli.add_command(create_initial_admin_comman)
```

2. RUN IN BASH:

```bash
flask create-admin
```

When you execute the command flask create-admin
It looks for your application instance app.py
It loads and executes the entire app.py script.
During the execution of app.py, when it hits your line import commands, the commands.py file is loaded,
and the custom command (create-admin) is registered with the Flask application instance.

Your app.py has this block at the end:

Python

if **name** == "**main**":
app.run(debug=True)

The sole purpose of this block is to start the development server when you run the file directly with python app.py.

When you run python app.py: The if condition is true, and the development server starts.

When you run flask create-admin: The if condition is false, the development server is not started, but the application is loaded into memory, making the db instance and the custom command available.

# -------------- LOGIN USER WITH FLASK-LOGIN------------------------

When you install Flask-Login and call:

```python
from flask_login import LoginManager

login_manager = LoginManager()
login_manager.init_app(app)
```

Flask-Login automatically creates a global context-aware variable named:

current_user

This variable is available:

in all your route functions

in all your Jinja templates (.html)

for every request, with the correct logged-in user

current_user.username
current_user.id
current_user.is_authenticated
current_user.is_active
current_user.is_anonymous

When you successfully log a user in using flask_login.login_user(user_object), Flask-Login takes the user's ID (user_object.id) and stores it securely in the session.

On every subsequent request, Flask-Login sees the ID in the session and calls your load_user(user_id) function, passing the stored ID.

Your function fetches the entire Users object from the database, allowing Flask-Login to set the global current_user proxy for that request.

# -----------------DESIGNING TABLES IN POSTGRES-------------------------

Your current horizontal structure is a design pattern known as an anti-pattern for several reasons.

That's an excellent question that gets to the heart of database normalization and optimal data modeling! The choice between a horizontal (wide) table and a vertical (tall) table depends heavily on how your data naturally behaves and how you plan to query it.
In your case, you should definitely switch to a vertical (normalized) table structure. Your current horizontal structure is a design pattern known as an anti-pattern for several reasons.

This design violates the principles of good database modeling:Schema Rigidity (Anti-Pattern):

Every time a new CPE type (e.g., a new modem model, stb_arr_6000) is introduced, you must perform a schema migration (ALTER TABLE ADD COLUMN). This is slow, risky, and requires application code changes.

Increased Query Complexity: Getting the latest record per city, as you are doing, is relatively complex but necessary. More importantly, calculating summary statistics (e.g., "What is the total number of STBs deployed across all cities?") requires summing up many columns, which is error-prone and inefficient.

Data Sparsity/Waste: If a specific city has zero units of stb_sky_44h, that column still exists and holds a 0 or NULL value for every record, wasting space and cache efficiency.

The Recommended Vertical (Normalized) Structure
The best practice is to normalize the data by moving the CPE type names into a separate lookup table and keeping the counts in a single column in your main record table.

```sql
CREATE TABLE cpe_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL  -- e.g., 'iads', 'stb_arr_4205', 'access_huaw', etc.
);

CREATE TABLE cpe_inventory (
    id SERIAL PRIMARY KEY,
    city_id INTEGER NOT NULL REFERENCES cities(id),
    cpe_type_id INTEGER NOT NULL REFERENCES cpe_types(id),
    quantity INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW(),
    -- Ensures only one record per CPE type per city (optional but good for inventory)
    CONSTRAINT uc_city_cpe UNIQUE (city_id, cpe_type_id)
);

```

Benefits of the Vertical Structure:

Flexibility (Scalability): To add a new CPE type, you simply insert a new row into the cpe_types table. No schema changes are needed for the cpe_inventory table.

Easier Queries: Aggregations are simple. To get the total inventory across all cities:

```sql
SELECT SUM(quantity) FROM cpe_inventory;
```

Smarter Storage: You only store records for CPE types that actually have a positive quantity for a given city, avoiding many 0 or NULL entries

Using Pivot Tables to Present Data

Your vertical table is excellent for storage and analysis, but the horizontal format is often better for reporting and presentation in your Flask app.

This is exactly where the PostgreSQL crosstab function becomes useful. You store the data vertically, and you use crosstab only for the final output step.

# -------- class SimplePagination:---------

IZ NEKOG RAZLOGA IMPORT pAGINATION FROM FLASK DOESNOT WOORK

```python
from flask_sqlalchemy import Pagination
```

A Pagination mi treba u :
def get_city_history_pivot():

Pa sam napravi SImplePagination classu koj simulira paginaciju:

```python
# paginate is iterable SimplePagination object
    paginate = SimplePagination(
        page=page, per_page=per_page, total=total_count, items=pivoted_data
    )
```

```python
 pagination = get_city_history_pivot(
        city_id=city.id, schema_list=schema_list, page=page, per_page=per_page
    )

    return render_template(
        "city_history.html",
        records=pagination,
        schema=schema_list,
        city=city,
    )
```

but records is your SimplePagination object
SimplePagination class returns the actual list inside:self.items, records.items
Stvarnu iteraciju vrsis po {% for r in records.items %}

# --------------------------------------------------------------------------

# ----------------------------------ABOUT APP DESIGN--------

In practice, your app is designed to function as a pivoted inventory dashboard. It takes "tall" data (one row per date/type) and turns it into "wide" data (one row per type, with dates as columns).

The defaultdict logic: Using defaultdict(int) in Python is a "defensive programming" win. It means if your template asks for a date that doesn't exist for a specific STB, it returns 0 instead of crashing your website.

# CROSS JOIN vs INNER JOIN

A CROSS JOIN (also known as a Cartesian Product) is the most "aggressive" way
to join tables. Unlike a regular join where you look for matching IDs,
a Cross Join tells the database: "Take every single row from Table A
and pair it with every single row from Table B."

Comparison with other Joins
To understand it better, think of how it differs from a standard INNER JOIN:

INNER JOIN: "Only give me rows where the City ID in Table A matches the City ID in Table B." (Filters data down).

CROSS JOIN: "I don't care about matches; I want every possible combination." (Explodes data up).

# OVO JE ZAPRAVO MUTIPLIKACIJA MATRICA

FROM
generate_series(1, 11) AS t(type_id)
CROSS JOIN
generate_series(1, 13) AS c(id)
CROSS JOIN (
-- Generate the last 4 Fridays
SELECT (date_trunc('week', NOW()) + interval '4 days' - (w || ' weeks')::interval)::date as friday_date
FROM generate_series(1, 4) w
) d

While the database doesn't care about the order,
If you were to swap them (e.g., City first, then CPE type), the result would be exactly the same. Because a CROSS JOIN is commutative ($A \times B$ is the same as $B \times A$), the final output doesn't change based on which one you write first.

# CHANGE IN CPE_INVENTORY RAW SQL--------------

The key realization (important)

You already know:

which CPE models you want to show

that each (city, cpe_type, week_end) is unique

that you’re aggregating a single week

That means:

You don’t need a pivot engine. You just need conditional aggregation.

Instead of pivoting rows into columns with crosstab(),
you use SUM(CASE WHEN ...).

```SQL
SUM(CASE WHEN cpe_type.name = 'MODEM' THEN quantity ELSE 0 END) AS "MODEM"
```

--Give me the latest week if we are in new week which doesnot have data yet

```sql
AND ci.week_end =(
SELECT MAX(ci2.week_end)
FROM cpe_inventory ci2
WHERE ci2.city_id=c.id
AND ci2.week_end <= :week_end
)
```

# -------------------------------------------------

Final rule (memorize this)

Snapshot table ⇒ always use MAX(week_end) ≤ target_date

If you follow this rule, your inventory logic will never break.

# ------------------------------------------------------------

Index rule you should always follow

Columns used in WHERE go first,
columns used for ordering/grouping go next.

--RECOMENDED INDEXSING IN CPE_INVENTORY:
--Look at your most common query patterns.

```sql

CREATE INDEX idx_cpe_dismantle_city_week
ON cpe_dismantle (city_id, week_end DESC);

CREATE INDEX idx_cpe_inventory_city_week_cpe
ON cpe_inventory (city_id, week_end DESC, cpe_type_id);
```

# cpe_dismantle--------------------------------

Final rule to remember (very important)

If a column changes the meaning of “one row” → it must be in the UNIQUE constraint

✔ quantity changes → no

✔ timestamps → no

✔ reason / category → YES

```sql
CREATE INDEX idx_cpe_dismantle_city_week
ON cpe_dismantle (city_id, week_end DESC);

```

Above index accelerates:

weekly snapshot

history pagination

“latest week ≤ X

```SQL
CREATE INDEX idx_cpe_dismantle_city_week_type
ON cpe_dismantle (city_id, week_end DESC, dismantle_type_id);
```

Above index is for:

per-type reports

filtered pivots

analytics by reason

If you filter on it regularly → index it
If it defines uniqueness → unique constraint
These are different concerns

Golden rule (again)

Any column that defines a “version” of data must be included in the latest-snapshot logic

Here:

week_end

dismantle_type_id

```sql
CREATE INDEX idx_cpe_dismantle_lookup
ON cpe_dismantle (city_id, week_end, dismantle_type_id, cpe_type_id);
```

# DIFFERENCE BETWEEN CROSS JOIN, LEFT JOIN AND JOIN IN SQL-----

Here are the key differences between these SQL join types:
CROSS JOIN

Returns the Cartesian product of both tables
Every row from the first table is combined with every row from the second table
If Table A has 10 rows and Table B has 5 rows, you get 50 rows
No JOIN condition is needed (or used)
Example: SELECT \* FROM employees CROSS JOIN departments

INNER JOIN (or just JOIN)

Returns only rows where there's a match in both tables based on the join condition
Most common type of join
If a row in either table doesn't have a matching row in the other, it's excluded
Example: SELECT \* FROM employees JOIN departments ON employees.dept_id = departments.id

LEFT JOIN (or LEFT OUTER JOIN)

Returns all rows from the left table, plus matching rows from the right table
If there's no match in the right table, the result still includes the left table row with NULL values for right table columns
Useful when you want to keep all records from one table regardless of matches
Example: SELECT \* FROM employees LEFT JOIN departments ON employees.dept_id = departments.id

Quick comparison with sample data:
If employees has Alice (dept 1), Bob (dept 2), Charlie (dept 3)
And departments has only dept 1 and dept 2:

INNER JOIN: Returns Alice and Bob only
LEFT JOIN: Returns Alice, Bob, and Charlie (Charlie's dept columns show NULL)
CROSS JOIN: Returns 9 rows (3 employees × 3 possible departments, ignoring the actual dept_id)

# --------------------------

🧠 Final takeaway

Database = facts
Query = selection
Python = shaping
HTML = grouping

# ---------dismantle_types AS TABLE OR ENUM--------

Your dismantle types are business data, not a programming constant

These are not just labels like "ASC" / "DESC".

They are:

displayed to users

possibly localized (language)

used in UI grouping

potentially extended later

That means:

They belong in data, not in schema code

Tables are made for this.

Final rule you can trust

If users can see it, filter by it, group by it, or you may extend it → use a table

# -------------- SQL -PYTHON STRUCTUREES----------------------------------------------------------------

# 5️⃣ Important rule (this is the key ⚠️)

SQL must never invent structure

Python must never invent data

You are respecting this rule ✔

# Layer Allowed to define

SQL quantities, aggregates, max week
Python structure, defaults, grouping
Template display only

DB (truth)
↓
Raw SQL (fast, correct)
↓
Python shaping (safe, explicit)
↓
Template (dumb, simple)

# Key principle to remember 🧠

Shaping code should be boring

If it feels clever, it’s too complex.

# 5️⃣ Golden rule (remember this)

Templates receive data, not rules

# That sentence maps exactly to the composite unique key.

Think of this table as:

“For THIS city, in THIS week, for THIS CPE, in THIS condition → quantity”

# Why NOT include quantity in UNIQUE

Because quantity:

changes over time

is the value, not the identity

# 🧠 Rule of thumb (remember this)

A column should be UNIQUE only if it fully identifies the row by itself.

# report_date: Using a DATE type instead of a full timestamp for the "week" makes it much easier to group data and prevents duplicate entries for the same week.

# TIMESTAMPTZ: Always use "timestamp with time zone" in Postgres to avoid headaches with server offsets.

# SQL responsibilities:

Fetch latest week, Aggregate per city
Produce totals per dismantle type

# Python responsibilities:

Split result set by dismantle_type_id,

# Render:

Complete table, Missing parts table (nested headers)

# --------------------------------------------------------------

# def cpe_dismantle_update():

#Temporal Snapshot with Partial Mutation

# STORAGE DB:

One physical table: cpe_dismantle

Rows represent:

(city, cpe_type, dismantle_type, week_end) → quantity

# Presentation (Views)

Two logical views (HTML tables):

Complete

Missing parts (NA / ND / NDIA)

These are views, not tables — this is exactly right.

# -------- STB RECORDS-------------------

# 🧠 Architectural verdict

Layer Responsibility Status
SQL Pivot + aggregation ✅ correct
Python Normalize shape ✅ correct
Template Display only ✅ correct

This is exactly how a Flask + SQL reporting page should be structured.

# Use this weeks list everywhere

SQL pivot aliases

grouping logic

template header rendering

This guarantees alignmen

# weeks is table structure, not data

weeks defines:

how many columns exist

their order

their labels

That is metadata about the table, not row data.

Your records are:

row values

quantities per week

Mixing structure with data leads to fragile templates.

# Final recommendation (clear answer)

✔ Keep passing weeks separately
✔ Treat it as table schema / metadata
✔ Do not infer structure from data

# +----------------------------------------------------------------------

# $ flask Endpoint Methods Rule

```bash
flask routes
```

auth.login GET, POST /login
auth.logout GET /logout
main.home GET /
static GET /static/<path:filename>
stb_inventory.stb_records GET /stb-records/
stb_inventory.update_iptv_users POST /stb-records/update_iptv_users
stb_inventory.update_stb_inventory POST /stb-records/update_stb
(.venv)

# Rule of thumb (worth remembering)

FOR FILTERS USE GET REQUEST + query parameter IN URL, NOT POST REQUEST

FOR NEW/Edits USE MODALS WITH POST REQUEST (NEW/EDIT REQUEST TO DB)

# in sql Rule:

Always filter before grouping
Always use week_end, not NOW() math in Python

# Index recommendation (very important for charts)

For good performance, make sure you have:

CREATE INDEX ON cpe_inventory (week_end);
CREATE INDEX ON cpe_inventory (city_id, week_end);
CREATE INDEX ON cpe_inventory (cpe_type_id, week_end);

If the table grows, this will matter a lot.

# -----------------------------------------------------------------------

# 1️⃣ What \_group_records() really is (important)

It is a domain transformation:

SQL rows
↓
\_city → cpe → damage → quantities

That structure:

```python
grouped[city]["cpe"][cpe]["damages"][damage_type]
```

is your canonical dismantle model.

✔ It merges SQL rows
✔ It resolves timestamps
✔ It normalizes dismantle types
✔ It’s presentation-agnos

# ADAPTER

Correct architecture (this is the key)
Keep \_group_records() as-is

Then create two adapters:

\_group_records()
↓
┌────────────────────┬────────────────────┐
│ HTML table adapter │ Excel export adapter│
└────────────────────┴────────────────────┘

HTML adapter IS TEMPLATE

# cpe record ukupno predzadnje, rasploziva oprema zadnje:

SQL
└─ calculates correct numbers

\_group_records()
└─ shapes data

\_reorder_cpe_records()
└─ presentation ordering

Jinja template
└─ rendering only

# This is enterprise-grade reporting design

get_cpe_inventory_pivoted() → numbers
\_group_records() → shape
\_reorder_cpe_records() → meaning
Excel formatting → appearance

# cities is_active:

Important rule for pivot queries

Always filter rows in the CTE, not after pivoting.

# --------------------------------------------------------------------------------------------------

# csrf token

Flask automatically checks CSRF token

INITIALIZE Before routes are used

```python
     csrf = CSRFProtect(app)
```

all POST, PUT, PATCH, DELETE requests are protected
If token is missing or invalid → Flask returns 400 Bad Request.
Every form that sends POST must include:

```html
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
```

IN API REQUEST:

```html
<!--CSRF token into page-->
<meta name="csrf-token" content="{{ csrf_token() }}" />
```

```js
   //Read CSRF token in JavaScript
  function getCsrfToken() {
  return document.querySelector('meta[name="csrf-token"]').getAttribute("content");
}
const res=await fetch("/cpe-records/update", {
      method:'POST',
      headers:{
        "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken()
      },
```

# ------------------------------------------------------------------------------------------

# report in pdf

cron
↓
/reports/weekly
↓
generate_pdf() → file
↓
send_email_report(file)

# when istalling weasyprint for pdf generating

OSError: cannot load library 'libgobject-2.0-0'
WeasyPrint requires native libraries:

GTK

Pango

Cairo

GObject

Fontconfig

Linux has these preinstalled.
Windows does not.

Download GTK for Windows
👉 GTK 3 Runtime (64-bit)
https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases

AFTER INSTALATION IT WORKS BUT IT GIVES ANYING WARNING IN CONSOLE.
SO TO SILENCE USE LAZY LOAD OF THIS HEAVY PACKET

```python
def generate_pdf(html):
    from weasyprint import HTML
    return HTML(string=html).write_pdf()
```

THIS WILL GENERATE WARNINGS ONLY WHEN USED

# ABOUT LAZY LOAD:

Lazy-load only “heavy / native / optional” libraries.

❌ Do NOT lazy-load everything.
✅ Do lazy-load libraries like WeasyPrint.
⚠️ Normal Python libraries like openpyxl do NOT need lazy loading.

# Why this matters for Gunicorn

Gunicorn forks workers.

If you import heavy libs at startup:

each worker loads them

RAM explodes

startup slow

worker timeout risk

# Lazy loading means:

workers start fast

heavy libs loaded only when needed

fewer crashes

easier scaling

This is production-level thinking.

# 🧠 Simple rule to remember

If a library touches the OS → lazy load it.
If it’s pure Python → normal import.

That rule alone will never betray you.

# WeasyPrint loads static assets from the filesystem, not Flask URLs.

WRONG (for PDF)

<link rel="stylesheet"
      href="{{ url_for('static', filename='reports/report.css') }}">

CORRECT (for WeasyPrint)

<link rel="stylesheet" href="static/reports/report.css">

# Correct architecture for charts in PDF

Postgres
↓
Python prepares chart data
↓
Chart rendered to image (PNG)
↓
PDF embeds <img src="...">

# Server-side charts (Python) (matplotlib):

# Final recommended flow for weekly report

weekly_report()
├─ fetch aggregated data
├─ generate summary numbers
├─ generate chart images (PNG)
├─ save images to static/reports/charts/
├─ render HTML with <img>
├─ generate PDF
└─ email PDF

# Important rule going forward

❌ Never write SQL just to compute something that can be derived from already loaded business data.

SQL is expensive.
Python logic is cheap and readable.

# AUTOMATIC EMAIL SEND:

Linux cron (or Windows Task Scheduler)
↓
python run_weekly_report.py
↓
Flask app context
↓
Check database config
↓
If enabled → generate & send
If disabled → exit silently

# cron job every 10min

Cron is only a trigger, not the scheduler
Your database (ReportSetting) is the scheduler.

```bash
*/10 * * * * curl -s -H "X-CRON-KEY: my-secret-key" http://localhost:5000/reports/weekly

```

# ------------------------------------------------------------------------------------------------------

# when we have mutiple datatsets we need this:

    # This line is a very efficient "Pythonic" way to perform three tasks at once:
    # extracting, de-duplicating, and ordering your data.
    # The Set Comprehension: {r.week_end for r in rows}
    # a set automatically enforces uniqueness.
    # The sorted() function takes the unique dates puts them in ascendin
    # By the end of the line, labels is a List (because sorted() always returns a list) that
    # contains every unique date found in your data, perfectly ordered from earliest to latest.

```python
	labels = sorted({r.week_end for r in rows})
```

# Think in layers:

Browser / HTML → Route (sanitize/convert) → Service (business logic) → DB

# 🧠 Mental model you can keep forever

Inventory table = event log
Python = snapshot builder
Charts = aggregation of snapshots

Once you think this way — everything is easy.

# carry forward

You only need carry-forward when your table stores sparse changes instead of full state.

Your cpe_inventory table is an event log → needed reconstruction.

# Final recommended mental model

Think of your system as:

📦 Weekly Inventory Snapshot

Each snapshot has:

• city
• week_end
• reported_at (timestamp of submission)
• many CPE rows

Even though stored flat in SQL.

#--------------------------------------------------------------------------

# 🚨 2. SQL injection risk in dynamic CASE columns

```python
f"WHEN ct.name = '{model["name"]}'"
```

# ATTACK

If someone ever inserts a CPE type name like:

```sql
test'; DROP TABLE cpe_dismantle; --
```

💥 goodbye database

Instead of injecting names directly, use IDs:

```sql
SUM(CASE WHEN ct.id = :cpe_id THEN cd.quantity ELSE 0 END)
```

#-------------------------------------------------------------------------

# POSTGRES index

If history grows large:

# Add index:

CREATE INDEX idx_cpe_dismantle_history
ON cpe_dismantle(city_id, dismantle_type_id, week_end DESC);

This will make your history view instant even with millions of rows.

# -------------------------------------------------------------------------

# ✔ Schema-driven columns

Using:

get_cpe_types_column_schema(...)

means:
✅ adding new CPE type requires ZERO SQL change
(this is pro-level design)

# The correct mental model for snapshot data

Inventory is a state, not an event.

So for any period:

If there’s no snapshot at the start → use the last known value before it.

This is how financial balances, stock levels, monitoring metrics, etc. are always plotted.

# ---------------------------------------------------------------------

# Users <-> Cities (many to many)

Which is lazy by default.

So SQLAlchemy will keep hitting DB unless you eager load.

selectinload is like “preloading images only when you will display them”.

```python

users = Users.query.options(selectinload(Users.cities)).order_by(Users.id).all()

```

# Then why do we even care about selectinload?

selectinload is for preventing many-object loops — not for single-user access.

Because of THIS scenario (10 USERS):

```python
users = Users.query.all()
return render_template("users.html", users=users)
```

SQLAlchemy runs:
1️⃣ Load user

```SQL
SELECT * FROM users;
```

That’s 1 query.

You now have 10 user objects in memory.

THAN BECAUSE OF:

```jinja
{% for user in users %}
{{ user.cities }}
{% endfor %}
```

First time template touches user.cities
2️⃣ Later (lazy load cities)

For User 1, SQLAlchemy runs:

```SQL
SELECT cities.* FROM cities
JOIN user_cities ...
WHERE user_id = 1;
```

For User 2, it runs again

```SQL
SELECT cities.* ... WHERE user_id = 2;
```

And so on…

Total queries:
1 (users)

- 10 (one per user)
  = 11 queries

That’s called N+1 PROBLEM:

N (users) + 1

# Why it matters more now

Before:

You had one city_id column — no relationship fetch.

Now:

You have:

Users <-> Cities (many to many)

Which is lazy by default.

So SQLAlchemy will keep hitting DB unless you eager load.

# ✅ What selectinload fixes

Users.query.options(selectinload(Users.cities))

Query 1 — all users
SELECT \* FROM users;

Query 2 — all related cities at once
SELECT cities.\*
FROM cities
JOIN user_cities ON ...
WHERE user_id IN (1,2,3,4,5...);

Boom. Done.
FOR 500 USERS
📈 From 500 queries → 2 queries

# You’ve now completely understood lazy loading vs eager loading.

# 🔐 Important takeaway

N+1 is only dangerous when:

loop over many parents

- access relationship inside loop

# --------------------------------------------------------------------------

# removed old compromised config.py from git repostory

# This removes the file from the 'tracking' index, not your hard drive

git rm --cached app/config.py

# Now commit that change

git commit -m "Remove sensitive config from tracking"

# Push to GitHub

git push origin main

# WORKING WITH .env FILE ON SERVER

Option A: Use a Volume Mount (Easiest for internal servers)
Keep the .env file on the server's hard drive in a secure folder (e.g., /opt/my-app/config/.env).

Update your docker-compose.prod.yml to point to it:

```YAML
services:
  flask:
    image: your-internal-registry/flask-app:latest
    env_file:
      - /opt/my-app/config/.env  # Path on the server
```

# --------------------------------------------------------------------

# SENDING EMAIL

Switche of using flask_mailman
When you use flask_mailman, you are trying to use SMTP (Port 587). In many corporate environments:

Port 443 (Web) is open for everyone (so you can use Webmail and Outlook).

Port 587 (SMTP) is blocked for security reasons to prevent "rogue" scripts or viruses from sending mass spam.

If SMTP (Port 587/25) is blocked even over VPN, the "corporate way" to send email over HTTPS (Port 443) without using the cloud is Exchange Web Services (EWS).

EWS is the "internal" API that Outlook itself uses to talk to Exchange. It is available on almost every corporate Exchange server at a specific URL.

For m:tel, your EWS endpoint is almost certainly:
https://webmail.mtel.ba/EWS/Exchange.asmx

```bash
curl -I https://webmail.mtel.ba/EWS/Exchange.asmx
```

Since flask_mailman only speaks SMTP, you would use a library called exchangelib. It is specifically designed for local corporate Exchange servers.

If you want your Flask app to send mail exactly like your browser or Outlook app does—bypassing the blocked SMTP ports—you should use Exchange Web Services (EWS).

Instead of flask_mailman, use the exchangelib library. It specifically uses Port 443.

# -----------------------------------------------------------------------------------

# START FLASK APP AFTER HOST MACHINE GOES DOWN (RESTART):

1. In docker-compose:

```yml
flask:
image: cpe-analiza-flask:latest
restart: unless-stopped
```

unless-stopped (Recommended) Starts the container on reboot only if it was running when the host went down. If you manually ran docker compose stop, it stays stopped.

2. Ensure Docker itself starts on boot

# Enable Docker to start on system boot

```bash
sudo systemctl enable docker
```

# -----------------------------------------------------------------------

# POSTGRES DATABASE PGDATA

On a standard Linux host, Docker stores named volumes in a protected directory:
/var/lib/docker/volumes/project_name_pgdata/\_data

Container Deletion: If you run docker compose down, the container is deleted, but the volume remains.

Container Update: When you pull a new postgres:17 image and restart, the new container "re-attaches" to that same folder, and all your CPE inventory data is still there.

. The "Nuclear" Command Warning
Be very careful with this command:

```Bash
docker compose down -v  # The -v deletes all volumes!
```

The -v flag (volumes) will wipe your database permanently. In production, always just use docker compose down

# ON REMOTE SERVER THERE ARE:

- THREE IMAGES
- docker-compose.prod.yml
- .env file (HIDDEN)

# -----------------------------------------------------------------------------------

# Logical Layering

# Database should:

Filter

Aggregate

Group

Pivot

# Python should:

Format

Group for template

Add presentation flags

# DUMP DB

# -------------------------------------------------------------

Docker creates a managed volume on the host machine.

```bash
docker volume inspect pgdata
```

/var/lib/docker/volumes/pgdata/\_data

# Recommended: Daily automated pg_dump

```bash
pg_dump -U myuser -h localhost -F c -f /backups/db_$(date +%F).dump mydb
```

or

```bash
pg_dump -U myuser -F c mydb > /network_storage/db_$(date +%F).dump
```

This:

Is compressed

Binary format

Can restore selectively

Usually smaller than DB size

Restore:

```bash
pg_restore -U myuser -d mydb backup.dump
```

# Backup without restore test = illusion of safety.

At least once:

createdb test_restore
pg_restore -d test_restore backup.dump

If it restores successfully → you're safe.

# How big is your database?

```sql
SELECT pg_size_pretty(pg_database_size('mydb'));

SELECT
    pg_database.datname,
    pg_size_pretty(pg_database_size(pg_database.datname)) AS size
FROM pg_database;

```

# ----------------------------------------------------------------------------

# Passwordless login link or Magic login link

flask-login uses session cookies.
Those cookies are:

Created after login

Stored in the browser

Signed with your secret key

Tied to a specific client

You cannot pre-generate a session cookie and embed it in email safely.

A temporary signed token → user clicks link → backend validates token → logs user in using login_user().

How It Works

You generate a signed token for the user

You email a link like:

https://yourapp.com/magic-login/<token>

User clicks link

Backend:

verifies token

logs user in with login_user(user)

redirects to dashboard

```bash
pip install itsdangerous

```

So to ensure your magic login respects 60 minutes:
session.permanent = True # ← IMPORTANT

# -------------------------------------------------------------

# Permanent session

If you do:

```python
session.permanent = True
```

Then Flask:

Uses PERMANENT_SESSION_LIFETIME

Sets cookie expiration timestamp

Enforces timeout (e.g. 60 minutes in your case)

Since you configured:

```python
PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)
```

PERMANENT_SESSION_LIFETIME does NOT automatically apply.

Many developers assume this config alone is enough:

```python
PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)
```

It is not.

It only works if:

```python
session.permanent = True
```

# ---------------------------------------------------------------------

# index

CREATE INDEX idx_cities_parent ON cities(parent_city_id);

# ---------------------------------------------------

ALTER TABLE cities
ADD COLUMN parent_city_id INT NULL REFERENCES cities(id);

# CPE_INVENTORT TABEL SADA IMA MAJOR CITY TABLE AND SUB CITIES TABLE

Banja Luka group
├ Banja Luka inventory
├ City A inventory
└ City B inventory

# Major City Total = Major City Inventory + All Sub-Cities

# IN MAJOR CITY CPE_INVENTORY QUERRY:

COALESCE(c.parent_city_id, c.id) AS major_city_id

produces:

| city_id | parent_city_id | major_city_id |
| ------- | -------------- | ------------- |
| 1       | NULL           | 1             |
| 10      | 1              | 1             |
| 20      | 1              | 1             |

So all rows map to the same major city.

When you run:

GROUP BY major_city_id

Postgres calculates:

40 + 60 + 50 = 150

So the major city's own quantity is automatically included.

# IN SUBCITIES QUERY:

WHERE
c.id = :major_city_id
OR c.parent_city_id = :major_city_id

# Logica za prikaz cpe_inavntory table u onsou na is_active state:

Case 1
Banja Luka active
Warehouse A active
Warehouse B active

Result:Banja Luka (sum of A+B+parent)

Case 2
Banja Luka inactive
Warehouse A active

Result: Banja Luka (sum of A)

Parent still appears because data exists.

Case 3
Banja Luka inactive
Warehouse A inactive

Result: not shown No active data.

# Logica za subcities prikaz in subcities table za cpe_inventoru:

Case 2
Banja Luka inactive
Warehouse A active

Result: Only show Warehouse A active in subcities

In major table Parent still appears because data exists.

# secret in subcities query:

WHERE (c.id = :major_city_id OR c.parent_city_id = :major_city_id)
AND c.is_active = true

# You will have 3 queries in your CPE_INVENTORY system:

1️⃣ Major city overview
group by major_city_id
2️⃣ Subcity page
group by city_id
3️⃣ Major city history
group by week_end

# ----------------------------------------------------------------------------------------------

# DOCKER VOLUMEN PGDATA

```bash
docker volume ls


docker volume inspect cpe-analiza_pgdata

```

"Mountpoint": "/var/lib/docker/volumes/cpe-analiza_pgdata/\_data",

# BACKUP/RESTORE MYDB FORM POSTGRES CONTAINER:

1.Find id of Postgres docker container:

```sh
docker ps
```

3. Backup directly to host

```sh
docker exec <container> pg_dump -U <user> -F c -d <db_name> > test_backup.dump

```

4. Restore from docker container:

Clean restore (RECOMMENDED)

👉 Drop DB → recreate → restore

```sql
DROP DATABASE mydb;
CREATE DATABASE mydb;
```

```sh

docker exec -i <container> pg_restore -U <user> -d mydb < test_backup.dump


docker exec -i 4a6de36c2105 pg_restore -U postgres -d mydb < test_backup.dump
```

5. Alternative: Restore into test DB restore_test:

```Bash
docker exec -it <container> psql -U <user> -c "CREATE DATABASE restore_test;"

docker exec -i 4a6de36c2105 pg_restore -U postgres -d restore_test < test_backup.dump

docker exec -i 4a6de36c2105 pg_restore -U postgres -d mydb_test < mydb_backup.dump
docker stop 740d60fedd12
docker start 740d60fedd12
```

# ---------------------------------------------------------------------------------------------------------

# ----------- FINAL BACKUP -----------------

```Bash
docker exec -i 4a6de36c2105 pg_dump -U postgres -F c -d mydb > mydb_backup.dump
```

# ----------- FINAL RESTORE -----------------

mydb must be empty

```Bash
docker exec -i 4a6de36c2105 pg_restore -U postgres -d mydb < mydb_backup.dump
```

# ----------- FINAL BACKUP INTO REMOTE PC DESKTOP -----------------

```Bash
scp root@10.198.3.92:/home/CPE-ANALIZA/mydb_backup1.dump .
```

# ----------------------.env file-------------

env_file:

- .env

All variables in .env are loaded into the container

environment:
TZ: Europe/Belgrade
DB_HOST: db
DB_PORT: 5432

These are added to the container environment

Can override values from env_file

env_file:

- .env
  environment:
  DB_NAME: mydb_test

DB_NAME in the container = mydb_test (overrides .env)

# ------------

# yep — this is one of those classic “ghost data” bugs that can eat hours 😄

# Clean up your current data - OBRISI GDIJE NEMA GRADA

```sql
DELETE FROM cpe_inventory
WHERE city_id NOT IN (SELECT id FROM cities);

```

The real fix (important)

You should enforce this at database level, not just app level.

✅ Add proper FK constraint

If not already present:

ALTER TABLE cpe_inventory
ADD CONSTRAINT fk_cpe_inventory_city
FOREIGN KEY (city_id)
REFERENCES cities(id)
ON DELETE RESTRICT;

or if you prefer cleanup:

ON DELETE CASCADE

# ----------------------------------------------

You moved from:

cities = data + behavior ❌

to:

cities = data
city_visibility_settings = behavior ✅

👉 This is clean architecture

ALTER TABLE cities
DROP COLUMN IF EXISTS is_active,
DROP COLUMN IF EXISTS include_in_total;

# -------------------------------------------------

# cascade delete city only for visibility_settings tablE

U SQLALCHEMY MODELU:

```sql

class CityVisibilitySettings(db.Model):
	city_id = mapped_column(
		ForeignKey("cities.id", ondelete="CASCADE"),
		nullable=False
	)

	city = relationship(
		"Cities",
		backref="visibility_settings",
		passive_deletes=True
	)
```

NA ZIVOJ BAZI:

ALTER TABLE city_visibility_settings
DROP CONSTRAINT city_visibility_settings_city_id_fkey;

ALTER TABLE city_visibility_settings
ADD CONSTRAINT city_visibility_settings_city_id_fkey
FOREIGN KEY (city_id)
REFERENCES cities(id)
ON DELETE CASCADE;

cities
↓ (CASCADE only here)
city_visibility_settings

cities
↓ (RESTRICT)
cpe_inventory
cpe_dismantle
access_inventory

# ----UPDATE AND DELETE SQL STATEMENT--------------------

```SQL
UPDATE cpe_inventory
SET quantity = 150
WHERE city_id = 3
  AND cpe_type_id = 1
  AND week_end = '2026-03-20';

DELETE FROM cpe_inventory
WHERE city_id = 3
  AND cpe_type_id = 1
  AND week_end = '2026-03-13';
```

# ----------- COMPLEXITY OF CPE_DISMANTLE QUERY------------------------------

You’re absolutely right — the query became complex because the logic is complex (hierarchy + “latest value” + “this week status” + conditional aggregation).

Understanding the Query Flow
Your query is essentially performing a "Pivot-on-the-fly." Here is how the data flows and where it gets stuc

Stage,What happens,Performance Cost
latest_data,Finds the most recent data point for every city.,High (due to the MAX subquery)
this_week_updates,Checks if data was touched this specific week.,Medium (requires index on week_end)
Main Result,Groups and Pivots (the CASE columns).,Low (mostly CPU work in Python/Postgres)
UNION ALL,Adds the 'UKUPNO' (Total) row.,Low

AFTER OPTIMIZATION:

1.WITH ranked_dismantle AS (...) – Common Table Expression (CTE)

ranked_dismantle,"The ""Latest Filter."" It ignores the 5-year history and only keeps the ""current"" state for each CPE.",Uses the index to ignore 99% of the 195k rows immediately.
So, for each combination of (city_id, cpe_type_id, dismantle_type_id), you get the most recent row before or on :week_end.

latest_data,"The ""Enrichment Center."" It attaches City names, CPE names, and Visibility settings to those latest rows.",Joins are performed on a significantly smaller subset of data.

this_week_updates,"The ""Status Checker."" It looks only at the current week_end to see if a user actually typed in data this week.",Aggregates only a tiny slice of the table (one specific date).

subcity_counts,"The ""Hierarchy Map."" It counts how many sub-cities belong to a major city.",Completely independent of the 195k dismantle rows; very fast.

# WHY PIVOTING?

Instead of having a row for every CPE type (which would make your Jinja template loop forever), we use CASE statements to "flip" the data horizontally.

Pivoting: We turn quantity where cpe_name = 'Router' into a column named "Router".

1. The Python "Pivot" Logic
   Your SQL query returns a "long" format (one row per city per dismantle type).

2. Flask Grouping
   Your \_group_records function transforms this into a "deep" JSON-like structure that your Jinja template can easily iterate over.

# ------------INDEX--------------------------------------------------

HOW TO SEE INDEXSES IN TABLE:

```SQL
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename;


SELECT *
FROM pg_indexes
WHERE tablename = 'cpe_inventory';
```

# CPE DISMANTLE INDEX

```SQL

-- 🔥 critical
CREATE INDEX idx_cpe_dismantle_lookup
ON cpe_dismantle (
    city_id,
    cpe_type_id,
    dismantle_type_id,
    week_end DESC
);

-- 🔥 weekly aggregation
CREATE INDEX idx_cpe_dismantle_week
ON cpe_dismantle (week_end, city_id, dismantle_type_id);

CREATE INDEX idx_cpe_dismantle_week_end ON cpe_dismantle (week_end);

-- 🟡 optional (keep only if chart is slow)
CREATE INDEX idx_cpe_dismantle_chart
ON cpe_dismantle (city_id, week_end, cpe_type_id);
```

# cpe_inventory

```sql


CREATE INDEX idx_cpe_inventory_lookup
ON cpe_inventory (
    city_id,
    cpe_type_id,
    week_end DESC
);

```

# cpe_broken

```sql


CREATE INDEX idx_cpe_broken_lookup
ON cpe_broken (
    city_id,
    cpe_type_id,
    week_end DESC
);

```

# CITIES INDEX

```SQL
CREATE INDEX idx_cities_parent
ON cities (parent_city_id);
```

# city_visibility_settings

```SQL
CREATE INDEX idx_city_visibility_main
ON city_visibility_settings (city_id, dataset_key);
```

# cpe_types

```SQL

CREATE INDEX idx_cpe_types_visible
ON cpe_types (visible_in_dismantle);

```

# User activity table:

```sql
CREATE INDEX idx_user_activity_timestamp
ON user_activity (timestamp);
```

# INDEX FOR CPE_DISMANTLE HISTORY

```SQL
CREATE INDEX idx_cpe_dismantle_history
ON cpe_dismantle(city_id, dismantle_type_id, week_end DESC);
```

# access_inventory

```SQL
CREATE INDEX idx_access_inventory_lookup
ON access_inventory (access_type_id, city_id, month_end);

CREATE INDEX idx_access_inventory_updated
ON access_inventory (updated_at);
```

# stb_inventory

```SQL
CREATE INDEX idx_stb_inventory_lookup
ON stb_inventory (stb_type_id, week_end);
```

# --------------------------------------------------------------------------------------

# CRON JOB FOR EVERY DAY TO CLEAN USERACTIVITY TABLE. LOGS OLDER THAN 4 MONTHS

# 2 (Hour): At 2 AM

```bash
0 2 * * * docker exec -i 4a6de36c2105 \
psql -U postgres -d mydb \
-c "DELETE FROM user_activity WHERE timestamp < NOW() - INTERVAL '4 months';"
```

# ---------------------------------------------------------------------------------------

# Grouping in cpe_dismantle history

Because your SQL query already does:

```sql
GROUP BY week_end, dismantle_code
```

Each row represents:

👉 one week + one damage type + all CPE columns

So grouping in flask just merges:

(comp row + nd row + na row + ndia row) → into one week object.

week_end+(comp row + nd row + na row + ndia row)+ all CPE columns -> ONE ROW IN CPE_DISMANTLE JINJA TABLE

# -------SYNC SCRIPT FOR IPTV PLATFORM-------------------------------------

IPTV PLATFORM is External service = only gives current snapshot

Cron → FLASK Sync script/service → External API → DB

1. ADD NEW SQLALCHEMY MODEL STBExternalMap

2. EXTERNAL API

# http://10.152.0.17:8090/

# http://10.152.0.17:8090/api/device-models

# http://10.152.0.17:8090/api/total-users

3. ADD CRON JOB

RUN AT 4AM

```bash
0 4 * * * docker exec -i cpe-analiza-flask-1 python -m flask sync-with-iptv
```

EVERY HOUR

```SQL
0 * * * * docker exec -i cpe-analiza-flask-1 python -m flask sync-with-iptv
```

Test manually

```bash
docker exec -it cpe-analiza-flask-1 flask sync-with-iptv
```

3. ADD SCRIPT IN "cli/sync_iptv.py WITH FLASK CLI DECORATOR

4. ADD SYSTEM USER: username="system" with id=0 FOR LOGINIG

```sql
insert into users (id, username, password_hash,role ) values(0, 'system','', 'user_iptv' )
```

# ------------------------------------------------------------------------------

# CRONTAB

```bash
crontab -l

EDITOR=nano crontab -e

CTRL-O
ENTER
CTRL-X

crontab -l
```

# -------------------------------timezone------------

# DateTime(timezone=True),

TIMESTAMP WITH TIME ZONE (timestamptz) — Postgres stores everything as UTC internally and converts on read. In this case, store UTC from Flask, Postgres handles the rest. ✅ Recommended.

DateTime(timezone=True) maps to timestamptz in Postgres, and func.now() runs on the Postgres side — so it uses whatever timezone Postgres is configured with (Belgrade in your case).
Since you're using server_default=func.now(), the timestamp is generated by Postgres, not Flask, so Flask's TZ setting doesn't even matter for these columns. Postgres writes the time, stores it as UTC internally, and returns it timezone-aware.

The flow is:
Flask → stores UTC → Postgres (stores UTC internally) → displays in Belgrade time

Flask generates datetime.now(timezone.utc) — explicitly UTC
Postgres receives UTC, stores UTC internally (that's what timestamptz always does regardless of timezone setting)
Postgres timezone = Europe/Belgrade — affects how NOW() and timestamps are displayed when you query directly (e.g. in pgAdmin you'll see Belgrade time)
Your users see Belgrade time when you convert on the way out with .astimezone(ZoneInfo("Europe/Belgrade"))

in docoker compose, this command is only on reading postgres db:
it convert internal utc data in db to Belgrade timzone

```yml
command: ["postgres", "-c", "timezone=Europe/Belgrade"]
```

```bash
docker exec -it fdb4475de1cb psql -U postgres -d mydb -c "ALTER DATABASE mydb SET timezone TO 'Europe/Belgrade';"
```

# -------------------------------------------------

ADDED HELPER TABLE FOR CPE DISMANTE tablename='dismantle_city_week_update',

The "Helper Table" pattern is a standard architectural choice called a Materialized View (Manually Managed) or a Status Ledger. It decouples your raw data (cpe_dismantle) from your reporting logic (city_week_update).

# cross join inisde cpe_dismantle

Why this works:
Logical Flow: By CROSS JOIN-ing dismantle_types and cpe_types first, you create a grid of every possible combination.

No more NULL filtering: Since dt.id and ct.id come from the CROSS JOIN (which always exists), your LEFT JOIN rd can fail (return NULL) without breaking the whole row.

New Cities: A new city will pass the visibility check, get paired with all dt and ct types via the CROSS JOIN, find no rd data, and correctly show 0 for all quantities.

Method,What happens to a New City?,Template Result
Current (LEFT JOIN),Row is filtered out by WHERE dt.group_name.,The city is invisible.
CROSS JOIN,Row is kept; quantity becomes 0.,The city appears with 0s under every model.

# CHANGE FORM LEFT JOIN TO CROSS JOIN:

Step,|"Your Current ""Data-First"" Join",|"The ""Structure-First"" (Cross Join)"
Visibility|,City passes (Visible = True),|City passes (Visible = True)
Types|,Waits for data to tell it which type it is.|,Forces the city to have a 'complete' or 'missing' slot immediately.
Data Join,|Tries to find a match (Finds nothing).|,Tries to find a match (Finds nothing).
WHERE Filter,|Checks NULL == 'complete' (False).|,Already filtered during the Join.
Result,|CITY HIDDEN,|CITY SHOWN (with 0s)

# -------------------------------------------------------------------------------------------------

# MODIFY ON LIVE USER ACTIVITY TABLE SO THAT DELETATION OF USER MAKE USER_ID=NULL in USER_ACTIVITY

# --------------------------------------------------------------------------------------

```SQL
ALTER TABLE user_activity
ALTER COLUMN user_id DROP NOT NULL;

-- 2. Remove the old CASCADE constraint
ALTER TABLE user_activity
DROP CONSTRAINT user_activity_user_id_fkey;

-- 3. Add the new SET NULL constraint
ALTER TABLE user_activity
ADD CONSTRAINT user_activity_user_id_fkey
FOREIGN KEY (user_id)
REFERENCES users(id)
ON DELETE SET NULL;
```

# IN MODAL

```PYTHON
user_id: Mapped[int] = mapped_column(
ForeignKey("users.id", ondelete="SET NULL"), nullable=True
)

# SQLAlchemy will now set user_id to None when the user is deleted
user = relationship("Users", backref="activities")
```

# --------------------------------------------------------------------------------

# MANY TO MANY

The short answer is no. You will not see a cities column in the users table, nor a users column in the cities table within PostgreSQL.

In a relational database, Many-to-Many relationships are handled through a third table—the Association Table—rather than columns within the primary tables.

How it works in Postgres
When you look at your database schema via a tool like psql, pgAdmin, or DBeaver, here is what you will actually find:

The users table: Contains only direct attributes like id, username, password_hash, role, etc.

The cities table: Contains id, name, parent_city_id, type, etc.

The user_cities table: This is the table you defined at the bottom of your code. This is the only place where the connection between a user and a city is stored.

Why don't the columns exist?
In SQLAlchemy, the relationship() function is a high-level abstraction.

At the Python level: SQLAlchemy makes it look like user.cities is a property or a list. When you access it, SQLAlchemy behind the scenes runs a SQL query to join users with user_cities and cities.

At the SQL level: Databases cannot store "lists" or "collections" inside a standard column effectively (without using complex types like JSONB or Arrays, which break standard relational rules).

# -------------------------------------------------------------------------------------------

# CPE AND CITY PERMISOONS FOR USERS:

# -------------------------------------------------------------------------------------------

# CPE AND CITY PERMISOONS FOR USERS IS ACHIEVE WITH TWO MANY TO MANY POSTGRES TABLE:

# user_cities,

# user_cpe_types

You currently have:

Permission Behavior if empty:
cities ❌ NO access
cpe_types ✅ FULL access

Current meaning:
Cities → restrictive (explicit assignment required)
CPE types → permissive (optional restriction layer)

It means:

Cities = scope boundary (must always be defined)
CPE types = fine-grained filter (optional)

👉 This matches real-world roles like:

“User works only in Banja Luka”
“User can edit only routers, not modems”

# ------------------------------------------------------------------------------

# SISTEM EMAIL NOTIFIKACIJE ZA KORISNIKE

# ------------------------------------------------------------------------------

1. User model extend:

```python
email: Mapped[str] = mapped_column(String(255), nullable=True, unique=True)
last_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

```

# Nedd also to ALTER POSTGRES TABLE

```sql

ALTER TABLE users
ADD COLUMN email VARCHAR(255);

ALTER TABLE users
ADD CONSTRAINT uq_users_email UNIQUE (email);

ALTER TABLE users
ADD COLUMN last_notified_at TIMESTAMP WITH TIME ZONE;

CREATE INDEX idx_users_last_notified_at
ON users (last_notified_at);

```

2. CRON JOB ON HOST

```bash
00 10 * * 4,5 docker exec -t <container_name_or_id> flask notify_stale_city

```

# You already think in:

Route → Service → DB

Do same here:

CLI → Service layer

3. Flask CLI notification command script:
   user_notification_cli.py

4. Notification service layer:
   user_notify.py

Posible index:

```sql

CREATE INDEX idx_inventory_week_city
ON cpe_inventory (week_end, city_id);

```

Logic flow

DB (stale detection)
↓
Cities
↓
Users mapping (no N+1)
↓
Merge sources
↓
One email per user

# -----------------------------------------------------------------------------------------------

# ALL CRONTAB ON LINUX HOST

[root@localhost ~]# crontab -l

# Job za slanje sedmicnog izvjestaja top menadzeru (Svakih 10min poziva routu za provijeru slanja izvjestaja)

_/10 _ \* \* \* curl -s -H "X-CRON-KEY:xxmtel123" http://localhost:5000/reports/weekly >> /var/log/weekly-report.log 2>&1

# Job za backup postgres baze mydb (Svaki dan u 2:00am)

0 2 \* \* \* docker exec -i cpe-analiza-db-1 pg_dump -U postgres -F c -d mydb > /home/CPE-ANALIZA/mydb_backup.dump

# Job za brisanje logova korisnickih aktivnosti u postgres tabeli user_activity starijih od 1 mjesec (Svaki dan u 3:00am)

0 3 \* \* \* docker exec -i cpe-analiza-db-1 psql -U postgres -d mydb -c "DELETE FROM user_activity WHERE timestamp < NOW() - INTERVAL '1 month';"

# Job za sinhrinizaciju stanja IPTV platforme i lokalne baze stb opreme (Svakih 4 sata poziva API)

0 _/4 _ \* \* docker exec -i cpe-analiza-flask-1 python -m flask sync-with-iptv

# Job za slanje notifikacija korisnicima o neosvijezenim stanjima skladista (Cetvrkom, Petkom u 10:00am)

00 10 \* \* 4,5 docker exec -i cpe-analiza-flask-1 python -m flask notify_stale_city

# --------------------------------------------------------------------------------------

# CERTIFICATE za SLANJE EMAIL KORISTECI exchangelib

1. mtel_bundle.pem

2. This is not mandatory

```Dockerfile
RUN cp mtel_bundle.pem /usr/local/share/ca-certificates/mtel_bundle.crt \
    && update-ca-certificates
```

3. ssl_adapter.py

But since the corporate server sends only the leaf cert, the most bulletproof fix is to use the MtelHttpAdapter approach in your Flask script — this forces requests to use your bundle which contains the full chain, bypassing the system store entirely:

This works because requests with an explicit verify= path will use the intermediates from your bundle to complete the chain — even when the server doesn't send them. This i
