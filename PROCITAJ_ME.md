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

# ---------------------IN LOCAL PRODUCTION DEVELOPMENT---------------

# docker compose -f docker-compose.prod.localy.yml up -d --build

# docker compose -f docker-compose.prod.localy.yml build --no-cache

# -----------------------IN PRODUCTION----------

# EXPORT DOCKER IMAGES:

# docker save -o ~/Desktop/cpe-analiza-flask.tar cpe-analiza-flask:latest

# scp docker-compose.prod.yml

# scp cpe-sip-nextjs-app.tar

# TOKOM DEVELOPMENTA

# dockerizuje only postgres and pgadmin

```bash
docker compose -f docker-compose.dev.yml up -d
```

# dockerizuje flask, postgres and pgadmin

```bash
docker compose -f docker-compose.prod.localy.yml up -d
docker compose -f docker-compose.prod.localy.yml up -d --build
```

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
from typing import Optional
import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    text,
    Enum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from flask_sqlalchemy import SQLAlchemy
import enum
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

# 1. Define a Python Enum (this stays in sync with DB)
class CpeTypeEnum(enum.Enum):
    IAD = "IAD"
    ONT = "ONT"
    STB = "STB"
    ANTENA = "ANTENA"
    ROUTER = "ROUTER"
    SWITCH = "SWITCH"
    WIFI_EXTENDER = "WIFI EXTENDER"
    WIFI_ACCESS_POINT = "WIFI ACCESS POINT"
    PHONES = "PHONES"
    SERVER = "SERVER"
    PC = "PC"
    IOT = "IOT"

class CpeTypes(db.Model):
    __tablename__ = "cpe_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    label: Mapped[Optional[str]] = mapped_column(String(200))

    # 2. Use the Enum type here
    # native_enum=True tells Postgres to create a custom TYPE
    type: Mapped[Optional[CpeTypeEnum]] = mapped_column(
        Enum(CpeTypeEnum, native_enum=True, name="cpe_type_enum")
    )

    is_active: Mapped[Optional[bool]] = mapped_column(
        Boolean, server_default=text("true")
    )

    cpe_dismantle: Mapped[list["CpeDismantle"]] = relationship(
        "CpeDismantle", back_populates="cpe_type"
    )
    cpe_inventory: Mapped[list["CpeInventory"]] = relationship(
        "CpeInventory", back_populates="cpe_type"
    )


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

```sql
CREATE EXTENSION IF NOT EXISTS tablefunc;
```

Your vertical table is excellent for storage and analysis, but the horizontal format is often better for reporting and presentation in your Flask app.

This is exactly where the PostgreSQL crosstab function becomes useful. You store the data vertically, and you use crosstab only for the final output step.

The crosstab function typically takes one or two SQL queries as text arguments (passed inside $$-delimited strings) and returns the pivoted result. The structure you provided is the one-argument form:

```sql

SELECT * FROM crosstab(source_sql_query) AS pivot_table(output_column_definitions)
```

This is the SQL query passed as the first argument to crosstab. It's responsible for fetching the raw data in the vertical format needed for pivoting.

```sql
$$
SELECT
    c.name AS city, -- 1. Row Identifier (Row Header)
    s.name AS stb_model, -- 2. Category (Column Header)
    r.quantity -- 3. Value (Aggregation Value)
FROM dismantle_records r
JOIN cities c ON r.city_id=c.id
JOIN stb_types s ON r.stb_type_id=s.id
WHERE r.week_start = '2025-02-03'
ORDER BY 1,2
$$
```

THIS QUERY RETURN The source query must return exactly three columns

Position Role in Pivot Your Query's Column Description
1st Column Row Identifier city The value that remains constant on the left side (the new row header).
2nd Column Category stb_model The value that will be rotated to become the new column headers.
3rd Column Value quantity The aggregated value that goes into the intersection of the new row and column.

# This is the part that defines the structure and data types of the final, pivoted resu

AS pivot_table (
city text,
mag250 int,
mag410 int,
kaon int
);

# AS pivot_table: Assigns an alias to the result set returned by crosstab

# city text: Defines the first output column. This must match the Row Identifier column (c.name AS city) from the source query.

# mag250 int, mag410 int, kaon int: These are the new column headers. The crosstab function expects to find these exact values ('mag250', 'mag410', 'kaon') in the Category column (stb_model) of your source data. The type is int because it's aggregating the quantity (which must be an integer).

# crosstab:

```sql
--c, p, max_ts, are TABLES
SELECT
	c.name AS city_name, --iz c izberi name i nazovi ga city_name
	p.*, -- iz p izaberi sve
	max_ts.max_updated_at --iz max_ts izberi max_updated_at
FROM
	(
	-- Your existing PIVOT QUERY goes here (aliased as p)
		SELECT *
		FROM crosstab(
			$$
			SELECT
				city_id,
			    cpe_model,
			    quantity
			FROM
				(
				-- (Your Window Function query to get rn=1 data)
					SELECT
						r.city_id,
						s.name AS cpe_model,
						r.quantity,
						r.updated_at,
						-- Assigns a rank (1, 2, 3...) to records within each group
						ROW_NUMBER() OVER(
						-- Define the group: A unique combination of city and cpe_model
							PARTITION BY r.city_id, r.cpe_type_id
							ORDER BY r.updated_at DESC
						) AS rn -- rn IS NAME OF COLUMN
					FROM cpe_inventory r
					JOIN cpe_types s ON r.cpe_type_id=s.id
				) AS ranked_records --KREIRA TABELU SA KOLONAMA: city: cpe_model, quantity, rn, updated_at
			WHERE
				-- Select only the record ranked #1 (the most recent one) for each group
				rn=1
			ORDER BY
			    city_id,
			    cpe_model
			$$
		) AS pivot_table (
		city_id INTEGER, "H267N" int, "HG658V2" int, "Arris VIP4205" int, "Arris VIP1113" int, "ONT HUAWEI" int, "ONT NOKIA" int
		)
	)AS p
	--to displays names of city instead of city_id in pivot table
JOIN cities c ON c.id=p.city_id
--to add latest update_at COLUMN to pivot table
LEFT JOIN (
	-- Subquery to find the single latest update time for the entire city
	SELECT
		city_id,
		MAX(updated_at) AS max_updated_at
	FROM cpe_inventory
	GROUP BY
		city_id
) AS max_ts ON max_ts.city_id=p.city_id;
```

PRVA SQL TABELA:

```sql
SELECT
					R.CITY_ID,
					S.NAME AS CPE_MODEL,
					R.QUANTITY,
					R.UPDATED_AT,
					ROW_NUMBER() OVER (
						PARTITION BY
							R.CITY_ID,
							R.CPE_TYPE_ID
						ORDER BY
							R.UPDATED_AT DESC
					) AS RN
				FROM
					CPE_INVENTORY R
					JOIN CPE_TYPES S ON R.CPE_TYPE_ID = S.ID
			) AS RANKED_RECORDS
```

DRUGA SQL TABELA:

```SQL
SELECT
			city_id,
			cpe_model,
			quantity
		FROM
			(
				SELECT
					R.CITY_ID,
					S.NAME AS CPE_MODEL,
					R.QUANTITY,
					R.UPDATED_AT,
					ROW_NUMBER() OVER (
						PARTITION BY
							R.CITY_ID,
							R.CPE_TYPE_ID
						ORDER BY
							R.UPDATED_AT DESC
					) AS RN
				FROM
					CPE_INVENTORY R
					JOIN CPE_TYPES S ON R.CPE_TYPE_ID = S.ID
			) AS RANKED_RECORDS
		WHERE
			RN = 1
		ORDER BY
			CITY_ID
			$$
			) AS PIVOT_TABLE (
				CITY_ID INTEGER,
				"IADS" INT,
				"VIP4205_VIP4302_1113" INT,
				"VIP5305" INT,
				"DIN4805V" INT,
				"DIN7005V" INT,
				"HP44H" INT,
				"ONT_HUA" INT,
				"ONT_NOK" INT,
				"STB_DTH" INT,
				"ANTENA_DTH" INT,
				"LNB_DUO_TWIN" INT
			)
```

TRECA SQL TABELA:

```SQL
SELECT
			*
		FROM
			CROSSTAB (
				$$
		SELECT
			city_id,
			cpe_model,
			quantity
		FROM
			(
				SELECT
					R.CITY_ID,
					S.NAME AS CPE_MODEL,
					R.QUANTITY,
					R.UPDATED_AT,
					ROW_NUMBER() OVER (
						PARTITION BY
							R.CITY_ID,
							R.CPE_TYPE_ID
						ORDER BY
							R.UPDATED_AT DESC
					) AS RN
				FROM
					CPE_INVENTORY R
					JOIN CPE_TYPES S ON R.CPE_TYPE_ID = S.ID
			) AS RANKED_RECORDS
		WHERE
			RN = 1
		ORDER BY
			CITY_ID
			$$
			) AS PIVOT_TABLE (
				CITY_ID INTEGER,
				"IADS" INT,
				"VIP4205_VIP4302_1113" INT,
				"VIP5305" INT,
				"DIN4805V" INT,
				"DIN7005V" INT,
				"HP44H" INT,
				"ONT_HUA" INT,
				"ONT_NOK" INT,
				"STB_DTH" INT,
				"ANTENA_DTH" INT,
				"LNB_DUO_TWIN" INT
			)
	) AS P
```

CETVRTA I ZADNJA SQL TABELA:

```SQL
SELECT
	C.NAME AS CITY_NAME, --DODAJ CITY NAME
	P.*,--CIJELA PIVOT TABELA
	MAX_TS.MAX_UPDATED_AT --DODAJ ZADNJE VRIJEME
FROM
	(
		SELECT
			*
		FROM
			CROSSTAB (
				$$
                -- 1. SOURCE QUERY (Input must provide the (row_name, category, value))
		SELECT
			city_id,
			cpe_model,
			quantity
		FROM
			(
				SELECT
					R.CITY_ID,
					S.NAME AS CPE_MODEL,
					R.QUANTITY,
					R.UPDATED_AT,
                    -- Assigns a rank (1, 2, 3...) to records within each group
                    -- Window function to find the latest record per (city, cpe_model) group
					ROW_NUMBER() OVER (
                        -- Define the group: A unique combination of city and cpe_model
						PARTITION BY
							R.CITY_ID,
							R.CPE_TYPE_ID
                            -- Order the records within the group by most recent update firs
						ORDER BY
							R.UPDATED_AT DESC
					) AS RN --KOLONA SE ZOVE RN
				FROM
					CPE_INVENTORY R
					JOIN CPE_TYPES S ON R.CPE_TYPE_ID = S.ID
			) AS RANKED_RECORDS
		WHERE
        -- Select only the record ranked #1 (the most recent one) for each group
			RN = 1
		ORDER BY
			CITY_ID
			$$
			) AS PIVOT_TABLE (
                -- 2. OUTPUT DEFINITION (Must define all columns and data types)
				CITY_ID INTEGER,
				"IADS" INT,
				"VIP4205_VIP4302_1113" INT,
				"VIP5305" INT,
				"DIN4805V" INT,
				"DIN7005V" INT,
				"HP44H" INT,
				"ONT_HUA" INT,
				"ONT_NOK" INT,
				"STB_DTH" INT,
				"ANTENA_DTH" INT,
				"LNB_DUO_TWIN" INT
			)
	) AS P
	JOIN CITIES C ON C.ID = P.CITY_ID
	LEFT JOIN (--DODAL KOLONU LASTA DATE
		SELECT
			CITY_ID,
			MAX(UPDATED_AT) AS MAX_UPDATED_AT
		FROM
			CPE_INVENTORY
		GROUP BY
			CITY_ID
	) AS MAX_TS ON MAX_TS.CITY_ID = P.CITY_ID
```

Using Window Functions
This query uses the ROW_NUMBER() window function to assign a rank to each record within a city/CPE group based on the latest updated_at timestamp.

1. The Inner Query (Subquery)
   The inner query performs the joins and applies the window function:

PARTITION BY r.city_id, r.cpe_type_id: This tells PostgreSQL to treat every unique combination of city_id and cpe_type_id as a separate group (or "window").

ORDER BY r.updated_at DESC: Within each group, the rows are ordered by the updated_at column in descending order. This ensures the most recent record is always placed first.

ROW_NUMBER() OVER (...) AS rn: This function assigns the number 1 to the first record in the ordered partition (the latest update), 2 to the second, and so on.

The outer query simply selects all columns (city, cpe_model, quantity, updated_at) from the result of the inner query, but only where the assigned rank (rn) is equal to 1.

This effectively filters the dataset down to the single, most recent record for every combination of city and CPE model, giving you the current inventory snapshot.

Step 1: Find the Latest Inventory Snapshot (Inner Query)

The subquery aliased as ranked_records first retrieves all inventory records. The ROW_NUMBER() window function assigns rn=1 to the row that has the maximum updated_at time for every unique combination of city_id and cpe_type_id

Result: A dataset containing only the current quantity for every CPE model in every city.

Step 2: Prepare Data for Pivoting (Outer SELECT inside crosstab)

The outer SELECT within the crosstab function takes the result of Step 1 and selects only the three columns needed for the one-argument crosstab function:

Row Identifier: city

Category: cpe_model

Value: quantity

Step 3: Execute the Pivot (The crosstab Function)

The crosstab function receives the vertical data from Step 2 and performs the rotation:

It uses city to create the rows.

It takes the specific values listed in the output definition ("H267N", "HG658V2", etc.) from the cpe_model column and converts them into column headers.

It places the corresponding quantity value into the cell where the row and model intersect. Since the input is already pre-aggregated to the latest record (thanks to the rn=1 filter), crosstab simply handles the rotation, not further aggregation.

# ------------------------------------------------------

# FINAL STATIC RAW SQL FOR GETTING PIVOT TABLE FROM VERTICAL DB:

# ---------------------------------------------------

# raw SQL statement, as crosstab isn't a standard, ORM-mappable function

```PYTHON
SQL_QUERY = """
WITH latest_pivot AS (SELECT
		P.CITY_ID, -- <--- ADDED: City ID for ordering
		C.NAME AS CITY_NAME,
        P."IADS",
        P."VIP4205_VIP4302_1113",
        P."VIP5305",
        P."DIN4805V",
        P."DIN7005V",
        P."HP44H",
        P."ONT_HUA",
        P."ONT_NOK",
        P."STB_DTH",
        P."ANTENA_DTH",
        P."LNB_DUO_TWIN",
        MAX_TS.MAX_UPDATED_AT
FROM
	(
		SELECT
			*
		FROM
			CROSSTAB (
				$$
		SELECT
			city_id,
			cpe_model,
			quantity
		FROM
			(
				SELECT
					R.CITY_ID,
					S.NAME AS CPE_MODEL,
					R.QUANTITY,
					R.UPDATED_AT,
					ROW_NUMBER() OVER (
						PARTITION BY
							R.CITY_ID,
							R.CPE_TYPE_ID
						ORDER BY
							R.UPDATED_AT DESC
					) AS RN
				FROM
					CPE_INVENTORY R
					JOIN CPE_TYPES S ON R.CPE_TYPE_ID = S.ID
			) AS RANKED_RECORDS
		WHERE
			RN = 1
		ORDER BY
			CITY_ID
			$$
			) AS PIVOT_TABLE (
				CITY_ID INTEGER,
				"IADS" INT,
				"VIP4205_VIP4302_1113" INT,
				"VIP5305" INT,
				"DIN4805V" INT,
				"DIN7005V" INT,
				"HP44H" INT,
				"ONT_HUA" INT,
				"ONT_NOK" INT,
				"STB_DTH" INT,
				"ANTENA_DTH" INT,
				"LNB_DUO_TWIN" INT
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
-----------------------------------------------------------
-- adding total row to end of pivot table
--PRVA TABELA
-- Data Rows
SELECT * FROM latest_pivot
-- <--- FIX: Sort by ID (ASC), placing NULLs (the Total Row) at the end
--UNIRANA (NA ZACELJE PRVE TABLELE DODAJ ROWOVE OD DRUGE TABELE)
UNION ALL --This appends a new row to the result set.

--SA DRUGOM TABLEOM koja sadrzi samo jedan row
SELECT
	NULL::INTEGER AS CITY_ID, -- <--- ADDED: City ID is NULL for the total row
	'UKUPNO'::VARCHAR AS CITY_NAME,
	SUM("IADS") AS "IADS",
	SUM("VIP4205_VIP4302_1113") AS "VIP4205_VIP4302_1113",
	SUM("VIP5305") AS "VIP5305",
	SUM("DIN4805V") AS "DIN4805V",
	SUM("DIN7005V") AS "DIN7005V",
	SUM("HP44H") AS "HP44H",
	SUM("ONT_HUA") AS "ONT_HUA",
    SUM("ONT_NOK") AS "ONT_NOK",
    SUM("STB_DTH") AS "STB_DTH",
	SUM("ANTENA_DTH") AS "ANTENA_DTH",
    SUM("LNB_DUO_TWIN") AS "LNB_DUO_TWIN",
	NULL::TIMESTAMP AS MAX_UPDATE_AT-- Max_updated_at is NULL for the total row
FROM latest_pivot
ORDER BY
	CITY_ID ASC NULLS LAST;
```

# ------------------------------------------------------

# FINAL DYNAMIC RAW SQL FOR GETTING PIVOT TABLE FROM VERTICAL DB:

# ---------------------------------------------------

```python
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
                    $$
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
                    $$
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
        {selected_columns.replace('p.', '')}, -- Remove 'p.' alias as we are selecting directly from latest_pivot
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
```

Final SELECT Correction: The SELECT \* FROM latest_pivot was replaced with an explicit SELECT to match the column names in the UNION ALL. Crucially, I had to remove the p. alias from the selected_columns list in the final SELECT because you are selecting from the latest_pivot CTE, not the aliased subquery P.

# ---------ALL CITY HISTORY PIVOTING----------

```PYTHON
 # THIS IS THE QUERY FOR CROSSTAB FUNCTION
    # IT WILL FIND ALL PIVOTED DATAD FOR SELECTED CITY_ID
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

    # CRITICAL: We need to figure out which UPDATED_AT timestamps belong to the current page.
    # We do this using a subquery (distinct_updates) to find the timestamps, and then offset/limit.

    # WE FIND ALL THE PIVOTED DATA IN CROSSTAB AND THEN JOIN WITH distinct_updates TABLE
    # distinct_updates TABLE ACT AS A FILTER. DISPLAY ONLY PIVOTED DATA BUT FOR DATA IN
    # LIMIT AND OFFSET.
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
```

While the one-argument form is simpler to write, it can sometimes be slow or produce inconsistent results if not all categories (CPE names) appear in the source data for every single row ID (timestamp).

The two-argument form of CROSSTAB fixes this by providing an explicit list of expected columns (categories). This guarantees that your output table always has the same column structure, even if some categories are missing in the data for a specific timestamp.

```SQL
CROSSTAB(
    source_sql TEXT,  -- 1. The query that provides the data (Row ID, Category, Value)
    category_sql TEXT -- 2. A separate query that provides the explicit list of columns
)
```

Field Purpose Example
Row ID What defines a unique output row (the pivot key). R.UPDATED_AT
Category What defines the output columns. S.NAME ('IADS', 'VIP5305')
Value The value to fill the cells with. R.QUANTITY

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

RUCNI UNOS U CPE_INVENOTRI NOVOG ELEMENTA ILI POVECANJA POSTOJOCEG KVANTITETA:

1. AKO JE UNOS KVANTITE ZA CPE ELEMNT KOJI NE POSTOJI U CPE_INVENOTRY ONDA
   POPUNI SVE GRADOVE
2. AKO JE UNOS KVANTITEA ZA VEC POCTOJECI CPE ELEMENT ONDA
   NADJI ZADNJI UNOS ZA SVE GRADOVE I DODAJ NA NJEGA

# ----------------------------------ABOUT APP DESIGN--------

In practice, your app is designed to function as a pivoted inventory dashboard. It takes "tall" data (one row per date/type) and turns it into "wide" data (one row per type, with dates as columns).

STB_INVENTORY, ONT_INVENTORY
Database vs. Python: You are doing the "heavy lifting" (filtering the last 4 weeks) in SQL and the "formatting" (pivoting) in Python. This is a very efficient pattern for small-to-medium datasets.

The defaultdict logic: Using defaultdict(int) in Python is a "defensive programming" win. It means if your template asks for a date that doesn't exist for a specific STB, it returns 0 instead of crashing your website.

# ---for croostable in postgress------

```sql
CREATE EXTENSION IF NOT EXISTS tablefunc;
```

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

# -------------------------- RENDERNING HTML TABLE-----------

Why “conditional colspan / conditional <td>” is a bad idea even if it looks OK
1️⃣ HTML tables must be rectangular

Browsers tolerate broken tables, but they do not guarantee behavior.

What you are relying on:

browser auto-correction

undefined layout rules

coincidence that column counts match

This breaks easily when:

you add sorting

you add pagination

you add sticky headers

you export to Excel

Bootstrap updates

user uses different browser

# What IS acceptable (even recommended)

Conditional content, not conditional structure

This is the key distinction.

✔ Always render the same number of columns
✔ Always keep the same colspan layout
✔ Control meaning via content, style, or icons

This is robust, readable, and future-proof.

🧠 Think of it like this

You are building a report, not a free-form layout.

Reports must satisfy:

consistency

predictability

exportability

Conditional <td> violates all three.

# ----------------------------------------------

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

# report in pdf

cron
↓
/reports/weekly
↓
generate_pdf() → file
↓
send_email(file)

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

# problem with pip in windows AND HOLOW VENV

Activate: source .venv/Scripts/activate

Install: python -m pip install <package-name>

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
*/10 * * * * curl -s http://localhost:5000/reports/weekly

```
# MAIL SERVER Auth done via IP whitelist

MAIL_SERVER = "exchange.company.local"
MAIL_PORT = 25
MAIL_USE_TLS = False
MAIL_USE_SSL = False
MAIL_USERNAME = None
MAIL_PASSWORD = None
DEFAULT_FROM_EMAIL = "noreply@company.ba"