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
