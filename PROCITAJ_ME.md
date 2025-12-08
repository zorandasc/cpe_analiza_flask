# FOR GIT BASH:

# --CREATE NEW PEOJECT---

# python -m venv .venv

# ----ACIVATE ENVIROMENT-----

# source .venv/Scripts/activate

# --INSTA PACKETS----

# pip install Flask

# pip install -U Flask-SQLAlchemy -ORM LAYER

# pip install psycopg2-binary - POSTGRE DRIVER

# -------RUN LOCAL DEVELOPENT APP IN GIT BASH------------

# set DB_HOST=localhost

# docker compose -f docker-compose.dev.yml up -d

THIS RUN POSTGRES AND PGADMIN ON LOCAL DOCKER

# python app.py

THIS RUN FLASK APP LOCALO ON PC

# localhost:5000 (Flask)

# - POSTGRES DB IS RUNNING ON ----

# localhost:5432 (DB)

# -------PG ADMIN-----------

# Go to: http://localhost:5050

# Login with your pgAdmin credentials.

# Connect to your PostgreSQL server

# Right-click Servers → Register → Server

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

# -----------------------IN PRODUCTION----------

# EXPORT DOCKER IMAGES:

# docker save -o ~/Desktop/cpe-analiza-flask.tar cpe-analiza-flask:latest

# scp docker-compose.prod.yml

# scp cpe-sip-nextjs-app.tar

# docker compose -f docker-compose.prod.yml up -d

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

# --------------export access------------------------

# save as exel

# export with formating

# save exel as csv(utf-8)

# vs code save as utf-8 without bom

# define table

# upload csv

# ------------create table in pgadmin with sql----------------------

# Click once on mydb so it becomes highlighted (this selects the database)

# At the top menu click Tools → Query Tool

```sql
CREATE TABLE public.cpe (
    id            integer PRIMARY KEY,
    date_recorded date,
    mjesto        text,
    iad267        integer,
    stbarr4205    integer,
    stbarr5305    integer,
    stbekt4805    integer,
    stbekt7005    integer,
    stbsky44      integer,
    onthw         integer,
    ontno         integer,
    dth           integer,
    antena        integer,
    lnb           integer,
    datum         text
);
```

# refresh webbrowser

# impor/export on empty table

# upload .csv

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

#n modern cloud environments images are stripped down to be as small as possible.
#Tools like ping, telnet, nc (netcat), or curl are often not installed for security and size reasons.
#However, Bash is almost always available. This provides a "native" way to
#check connectivity without installing extra packages.
#bash -c "..."This runs a new instance of the Bash shell
#/dev/tcp/host/port: This is not a real file on the disk. It is a Bash built-in feature (a pseudo-device).
#When you redirect input or output to this path, Bash attempts to open a TCP socket to the specified host and port.
#The command following it (echo 'FAILED') runs only if the previous command sequence failed
bash -c "echo > /dev/tcp/db/5432 && echo 'OK' || echo 'FAILED'"

```

# CREATE MODEL FROM POSTGRES TABLES:

# --------------------------------------------------------

```bash
sqlacodegen postgresql://postgres:mypassword@localhost:5431/mydb > models.py
```

AND INSIDE models.py MAKE CHANGES:

```python
from flask_sqlalchemy import SQLAlchemy
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

CPE_TYPE_CHOICES = [
    "IAD",
    "ONT",
    "STB",
    "ANTENA",
    "ROUTER",
    "SWITCH",
    "WIFI EXTENDER",
    "WIFI ACCESS POINT",
    "PHONES",
    "SERVER",
    "PC",
    "IOT",
]

class CpeTypes(db.Model):
    __tablename__ = "cpe_types"
    __table_args__ = (
        CheckConstraint(
            sqltext=f"type::text = ANY (ARRAY[{', '.join(f"'{c}'::character varying" for c in CPE_TYPE_CHOICES)}]::text[])",
            name="cpe_types_type_check",
        ),
        PrimaryKeyConstraint("id", name="cpe_types_pkey"),
        UniqueConstraint("name", name="cpe_types_name_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[Optional[str]] = mapped_column(String(100))

```

# --------------------------------------

# CREATE ADMIN USER:

# --------------------------------------------------------

1. CREATE CLI FLASK FILE create_admin_cli.py

```python
@click.command("create-admin")  # Define the command name
@with_appcontext
def create_initial_admin(username="admin", plain_password="admin123"):
```

2. THEN IMPORT INISIDE app.py TO REGISTER COMMAND

# Flask will now register the 'create-admin' command

```python
# --- NEW: Import the command function and register it ---

1.
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

from flask_login import LoginManager

login_manager = LoginManager()
login_manager.init_app(app)

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

❌ Why the Current Horizontal Table is ProblematicYour existing cpe_records table structure is:idcity_idiadsstb_arr_4205stb_ekt_4805...lnb_duocreated_at110151012...32025-01-01

This design violates the principles of good database modeling:Schema Rigidity (Anti-Pattern):

Every time a new CPE type (e.g., a new modem model, stb_arr_6000) is introduced, you must perform a schema migration (ALTER TABLE ADD COLUMN). This is slow, risky, and requires application code changes.

Increased Query Complexity: Getting the latest record per city, as you are doing, is relatively complex but necessary. More importantly, calculating summary statistics (e.g., "What is the total number of STBs deployed across all cities?") requires summing up many columns, which is error-prone and inefficient.

Data Sparsity/Waste: If a specific city has zero units of stb_sky_44h, that column still exists and holds a 0 or NULL value for every record, wasting space and cache efficiency.

The Recommended Vertical (Normalized) Structure
The best practice is to normalize the data by moving the CPE type names into a separate lookup table and keeping the counts in a single column in your main record table.

```sql
CREATE TABLE cpe_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL  -- e.g., 'iads', 'stb_arr_4205', 'ont_huaw', etc.
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
