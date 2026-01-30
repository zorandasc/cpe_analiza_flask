from sqlalchemy import text
from app.extensions import db
from app.models import CpeTypes


def update_cpe_type(cpe_id, data):
    cpe = CpeTypes.query.get_or_404(cpe_id)

    # 1. Logic: Uniqueness check
    existing = CpeTypes.query.filter(
        CpeTypes.name == data["name"], CpeTypes.id != cpe_id
    ).first()
    if existing:
        return False, "Tip CPE opreme već postoji!"

    # 2. # Handle Reordering for Total
    new_total_order = int(data["order_total"]) if data["order_total"] else None
    old_total_order = cpe.order_in_total
    handle_display_order("order_in_total", cpe.id, old_total_order, new_total_order)
    cpe.order_in_total = new_total_order

    # Handle Reordering for Dismantle
    new_dismantle_order = (
        int(data["order_dismantle"]) if data["order_dismantle"] else None
    )
    old_dismantle_order = cpe.order_in_dismantle
    handle_display_order(
        "order_in_dismantle", cpe.id, old_dismantle_order, new_dismantle_order
    )
    cpe.order_in_dismantle = new_dismantle_order

    # 3. Update fields
    cpe.name = data["name"]
    cpe.label = data["label"]
    cpe.type = data["type"]
    cpe.header_color = data.get("header_color") or None
    cpe.has_remote = data.get("has_remote", False)
    cpe.has_adapter = data.get("has_adapter", False)
    cpe.visible_in_total = data.get("visible_in_total", False)
    cpe.visible_in_dismantle = data.get("visible_in_dismantle", False)

    try:
        db.session.commit()
        return True, "Cpe tip uspješno izmijenjen!"
    except Exception as e:
        db.session.rollback()
        return False, str(e)


def handle_display_order(column_name, cpe_id, old_order, new_order):
    """
    Reorders CPE type.

    column_name: 'order_in_total' or 'order_in_dismantle'

    Rules:
    - None -> number  : insert at position
    - number -> number: move within ordering
    """

    # Safety
    if new_order < 1:
        raise ValueError("display_order must be >= 1")

    # ----------------------------------
    # No change
    # ----------------------------------
    if new_order == old_order:
        return

    # ----------------------------------
    # First placement (None -> number)
    # ----------------------------------
    if old_order is None:
        db.session.execute(
            text(f"""
                UPDATE cpe_types
                SET {column_name} = {column_name} + 1
                WHERE {column_name} >= :new
            """),
            {"new": new_order},
        )
        return
    # ----------------------------------
    # Reordering
    # ----------------------------------
    if new_order < old_order:
        # moving UP
        db.session.execute(
            text(f"""
                UPDATE cpe_types
                SET {column_name} = {column_name} + 1
                WHERE {column_name} >= :new
                  AND {column_name} < :old
                  AND id != :id
            """),
            {"new": new_order, "old": old_order, "id": cpe_id},
        )

    else:
        # moving DOWN
        db.session.execute(
            text(f"""
                UPDATE cpe_types
                SET {column_name} = {column_name} - 1
                WHERE {column_name} > :old
                  AND {column_name} <= :new
                  AND id != :id
            """),
            {"new": new_order, "old": old_order, "id": cpe_id},
        )


# cpe inventory
def get_cpe_inventory_chart_data(city_id=None, cpe_id=None, cpe_type=None, weeks=None):
    params = {}
    conditions = []

    base_join = """
        FROM cpe_inventory i
        JOIN cities c ON c.id=i.city_id
        JOIN cpe_types ct ON ct.id=cpe_type_id
        WHERE 1=1
    """

    # ----------------------------
    # City logic
    # ----------------------------
    if city_id is None:  # filter by city
        # IF CITY ID IS NOT SELECTED THAN CALCULATE SUM ON ALL CITIES
        # BUT EXCLUDE RASPOLOZIVA OPREMA
        conditions.append("c.include_in_total = true")
    else:
        conditions.append("city_id = :city_id")
        params["city_id"] = city_id

    # ----------------------------
    # Weeks
    # ----------------------------
    if weeks:  # filter by weeks
        conditions.append("""
            i.week_end IN (
                SELECT DISTINCT week_end
                FROM cpe_inventory
                ORDER BY week_end DESC
                LIMIT :weeks
            )
        """)
        params["weeks"] = weeks

    where_clause = ""
    if conditions:
        where_clause = " AND " + " AND ".join(conditions)

    # ======================================================
    # 🔵 MODE C — specific CPE selected
    # ======================================================

    # 🔁 CASE 1 — one CPE selected → single dataset
    if cpe_id is not None:
        sql = f"""    
            SELECT 
                i.week_end,
                SUM(i.quantity) AS total
            {base_join}
            {where_clause}
            AND i.cpe_type_id = :cpe_id
            GROUP BY i.week_end
            ORDER BY i.week_end
        """
        params["cpe_id"] = cpe_id
        rows = db.session.execute(text(sql), params).fetchall()

        return {
            "labels": [r.week_end.strftime("%d-%m-%Y") for r in rows],
            "datasets": [
                {
                    "label": "Total",
                    "data": [r.total for r in rows],
                }
            ],
        }

    # ======================================================
    # 🟡 MODE B — CPE TYPE selected
    # ======================================================

    if cpe_type is not None:
        # 🔁 CASE 2 — no CPE selected → multiple datasets
        sql = f"""
        SELECT
                i.week_end,
                SUM(i.quantity) AS total
            {base_join}
            {where_clause}
            AND ct.type = CAST(:cpe_type AS cpe_type_enum)
            GROUP BY i.week_end
            ORDER BY i.week_end
        """
        params["cpe_type"] = cpe_type
        rows = db.session.execute(text(sql), params).fetchall()

        # get device list under that type
        devices_sql = """
            SELECT DISTINCT ct.name
            FROM cpe_types ct
            WHERE ct.type = CAST(:cpe_type AS cpe_type_enum)
            AND ct.visible_in_total = true
            ORDER BY ct.name
        """
        devices = db.session.execute(
            text(devices_sql), {"cpe_type": cpe_type}
        ).fetchall()

        devices = [cpe.name for cpe in devices]

        return {
            "labels": [r.week_end.strftime("%d-%m-%Y") for r in rows],
            "datasets": [
                {"label": f"Ukupno ({cpe_type})", "data": [r.total for r in rows]}
            ],
            "devices": devices,
            "mode": "type-total",
        }

    # ======================================================
    # 🟢 MODE A — nothing selected → GROUP BY TYPE
    # ======================================================
    sql = f"""
        SELECT
            i.week_end,
            ct.type,
            SUM(i.quantity) AS total
        {base_join}
        {where_clause}
        GROUP BY i.week_end, ct.type
        ORDER BY i.week_end
    """

    rows = db.session.execute(text(sql), params).fetchall()

    labels = sorted({r.week_end for r in rows})

    # ------------------------
    # Pivot for Chart.js
    # ------------------------
    # This line is a very efficient "Pythonic" way to perform three tasks at once:
    # extracting, de-duplicating, and ordering your data.
    # The Set Comprehension: {r.week_end for r in rows}
    # a set automatically enforces uniqueness.
    # The sorted() function takes the unique dates puts them in ascendin
    # By the end of the line, labels is a List (because sorted() always returns a list) that
    # contains every unique date found in your data, perfectly ordered from earliest to latest.

    datasets_dict = {}
    for r in rows:
        # setdefault checks if r.cpe_name exists. If it doesn't, it creates it
        # If it does exist, it does nothing and moves on.
        # This initializes an empty dictionary to hold your data
        # {"CPE_NAME", [DATE1:0, DATE2:0,...]}
        datasets_dict.setdefault(r.type, {lab: 0 for lab in labels})
        # Now that we are sure the dictionary for that specific cpe_name exists,
        # update its value from 0 to the actual total
        datasets_dict[r.type][r.week_end] = r.total

    # data_map dictonary looks like:
    # {
    #'Router_A': {'Jan 1': 10, 'Jan 8': 0, 'Jan 15': 5},
    #'Switch_B': {'Jan 1': 0, 'Jan 8': 20, 'Jan 15': 12}
    # . . .
    # }

    chart_datasets = []
    for cpe_type, values in datasets_dict.items():
        chart_datasets.append(
            # values[lab]  take only numbers
            {"label": cpe_type, "data": [values[lab] for lab in labels]}
        )
    # char_datasets look like:
    # "datasets": [
    # {"label": "CPE Router","data": [120, 140, 160] },
    # {"label": "CPE Modem","data": [80, 90, 110]},
    # ...]
    # }

    return {
        "labels": [l.strftime("%d-%m-%Y") for l in labels],
        "datasets": chart_datasets,
    }
    # RETRUN LOOK LIKE:
    # {
    # "labels": ["01-12-2025", "08-12-2025", "15-12-2025"],
    # "datasets": [
    # {"label": "CPE Router","data": [120, 140, 160] },
    # {"label": "CPE Modem","data": [80, 90, 110]},
    # ...]
    # }


# cpe dismantles
def get_cpe_dismantle_chart_data(
    city_id=None, cpe_id=None, cpe_type=None, dismantle_type_id=None, weeks=None
):
    params = {}
    conditions = []

    if city_id is not None:
        conditions.append("city_id = :city_id")
        params["city_id"] = city_id

    if cpe_id is not None:
        conditions.append("cpe_type_id = :cpe_id")
        params["cpe_id"] = cpe_id
    elif cpe_type is not None:
        # This tells Postgres explicitly This parameter is an enum, not text
        conditions.append("ct.type = CAST(:cpe_type AS cpe_type_enum)")
        params["cpe_type"] = cpe_type

    if dismantle_type_id is not None:
        conditions.append("dismantle_type_id = :dismantle_type_id")
        params["dismantle_type_id"] = dismantle_type_id

    where_clause = ""
    if conditions:
        where_clause = " AND " + " AND ".join(conditions)

    limit_clause = ""
    if weeks:
        limit_clause = """
            AND i.week_end IN (
                SELECT DISTINCT week_end
                FROM cpe_dismantle
                ORDER BY week_end DESC
                LIMIT :weeks
            )
        """
        params["weeks"] = weeks

    # 🔁 CASE 1 — one CPE selected → single dataset
    if cpe_id is not None:
        sql = f"""
            SELECT 
                i.week_end, 
                SUM(i.quantity) AS total
            FROM cpe_dismantle i
            WHERE 1=1
            {where_clause}
            {limit_clause}
            GROUP BY i.week_end
            ORDER BY i.week_end
        """

        rows = db.session.execute(text(sql), params).fetchall()

        return {
            "labels": [r.week_end.strftime("%d-%m-%Y") for r in rows],
            "datasets": [
                {
                    "label": "Total",
                    "data": [r.total for r in rows],
                }
            ],
        }

    # 🔁 CASE 2 — no CPE selected → multiple datasets
    sql = f"""
    SELECT 
        i.week_end,
        i.cpe_type_id,
        ct.name AS cpe_name,
        SUM(i.quantity) AS total
    FROM cpe_dismantle i
    JOIN cpe_types ct ON ct.id = i.cpe_type_id
    WHERE 1=1
    {where_clause}
    {limit_clause}
    GROUP BY i.week_end, i.cpe_type_id, ct.name
    ORDER BY i.week_end

    """

    rows = db.session.execute(text(sql), params).fetchall()
    # [ (datetime.date(2026, 1, 23), 6, 'Skyworth STBHD/4K HP44H', 375),...]

    # ------------------------
    # Pivot for Chart.js
    # ------------------------

    # This line is a very efficient "Pythonic" way to perform three tasks at once:
    # extracting, de-duplicating, and ordering your data.
    labels = sorted({r.week_end for r in rows})

    # This initializes an empty dictionary
    dataset_dict = {}
    for r in rows:
        # setdefault checks if r.cpe_name exists.
        # it creates it empty totals
        dataset_dict.setdefault(r.cpe_name, {lab: 0 for lab in labels})
        # # update its value from 0 to the actual total
        dataset_dict[r.cpe_name][r.week_end] = r.total

    # dataset_dict={('Router_A': {'Jan 1': 10, 'Jan 8': 0, 'Jan 15': 5})..,

    chart_datasets = []
    for cpe_name, values in dataset_dict.items():
        chart_datasets.append(
            # take only numbers
            {"label": cpe_name, "data": [values[lab] for lab in labels]}
        )
    # chart_datasets=[{"label":'Router_A', "data":[10, 0, 5]}..,]

    return {
        "labels": [lab.strftime("%d-%m-%Y") for lab in labels],
        "datasets": chart_datasets,
    }


# stb inventory
def get_stb_inventory_chart_data(stb_type_id=None, weeks=None):
    params = {}

    where = ""
    if stb_type_id:
        where = "AND stb_type_id= :stb_type_id"
        params["stb_type_id"] = stb_type_id

    if weeks:
        sql = f"""
            WITH last_week AS (
            SELECT DISTINCT week_end
            FROM stb_inventory 
            WHERE 1=1 {where}
            ORDER BY week_end DESC
            LIMIT :weeks
            )
            SELECT i.week_end, SUM(i.quantity) AS total
            FROM stb_inventory i
            JOIN last_week w ON w.week_end=i.week_end
            WHERE 1=1 {where}
            GROUP BY i.week_end
            ORDER BY i.week_end
        """
        params["weeks"] = weeks
    else:
        sql = f"""
            SELECT week_end, SUM(quantity) AS total
            FROM stb_inventory
            WHERE 1=1 {where}
            GROUP BY week_end
            ORDER BY week_end
        """

    rows = db.session.execute(text(sql), params).fetchall()

    return {
        "labels": [r.week_end.strftime("%d-%m-%Y") for r in rows],
        "datasets": [{"label": "STB Uređaji", "data": [r.total for r in rows]}],
    }


# iptv users charts
def get_iptv_inventory_chart_data(weeks=None):
    params = {}
    if weeks:
        sql = """
            WITH last_week AS (
            SELECT DISTINCT week_end
            FROM iptv_users 
            ORDER BY week_end DESC
            LIMIT :weeks
            )
            SELECT i.week_end, SUM(i.total_users) AS total
            FROM iptv_users i
            JOIN last_week w ON w.week_end=i.week_end
            GROUP BY i.week_end
            ORDER BY i.week_end
        """
        params["weeks"] = weeks
    else:
        sql = """
            SELECT week_end, SUM(total_users) AS total
            FROM iptv_users
            GROUP BY week_end
            ORDER BY week_end
        """

    rows = db.session.execute(text(sql), params).fetchall()

    return {
        "labels": [r.week_end.strftime("%d-%m-%Y") for r in rows],
        "datasets": [{"label": "IPTV korisnici", "data": [r.total for r in rows]}],
    }


# ont inventory
def get_ont_inventory_chart_data(city_id=None, months=None):
    params = {}

    where = ""
    if city_id:
        where = "AND city_id= :city_id"
        params["city_id"] = city_id

    if months:
        sql = f"""
            WITH last_month AS (
            SELECT DISTINCT month_end
            FROM ont_inventory 
            WHERE 1=1 {where}
            ORDER BY month_end DESC
            LIMIT :months
            )
            SELECT i.month_end, SUM(i.quantity) AS total
            FROM ont_inventory i
            JOIN last_month m ON m.month_end=i.month_end
            WHERE 1=1 {where}
            GROUP BY i.month_end
            ORDER BY i.month_end
        """
        params["months"] = months
    else:
        sql = f"""
            SELECT month_end, SUM(quantity) AS total
            FROM ont_inventory
            WHERE 1=1 {where}
            GROUP BY month_end
            ORDER BY month_end
        """

    rows = db.session.execute(text(sql), params).fetchall()

    return {
        "labels": [r.month_end.strftime("%d-%m-%Y") for r in rows],
        "datasets": [{"label": "ONT uređaji", "data": [r.total for r in rows]}],
    }


BASE_TABLES = {
    "cpe": "cpe_inventory",
    "cpe_dis": "cpe_dismantle",
    "stb": "stb_inventory",
    "ont": "ont_inventory",
}

JOIN_TABLES = {
    "city": {
        "table": "cities",
        "pk": "id",
        "cols": "j.id, j.name",
        "order_by": "j.name",
    },
    "cpe_type": {
        "table": "cpe_types",
        "pk": "id",
        "cols": "j.id, j.label",
        "order_by": "j.label",
    },
    "stb_type": {
        "table": "stb_types",
        "pk": "id",
        "cols": "j.id, j.label",
        "order_by": "j.label",
    },
    "dis_type": {
        "table": "dismantle_types",
        "pk": "id",
        "cols": "j.id, j.label",
        "order_by": "j.label",
    },
}


def get_distinct_joined_values(
    base_key: str,
    join_key: str,
    base_fk: str,
    extra_joins: str = "",
    where_clause: str = "",
    params: dict | None = None,
):
    base_table = BASE_TABLES.get(base_key)
    join_meta = JOIN_TABLES.get(join_key)

    if not base_table or not join_meta:
        raise ValueError("Invalid base or join table")

    params = params or {}

    join_table = join_meta["table"]
    join_pk = join_meta["pk"]
    select_cols = join_meta["cols"]
    order_by = join_meta["order_by"]

    sql = f"""
        SELECT DISTINCT {select_cols}
        FROM {base_table} b
        JOIN {join_table} j ON j.{join_pk}=b.{base_fk}
        {extra_joins}
        WHERE 1=1
        {where_clause}
        ORDER BY {order_by}
    """

    return db.session.execute(text(sql), params).fetchall()


# ONE EXAMPLE OF get_distinct_joined_values() FUNCTION ABSTRACTION:
"""
SELECT DISTINCT c.id, c.name
FROM ont_inventory i
JOIN cities c ON c.id = i.city_id
ORDER BY c.id
"""
"""
SELECT DISTINCT t.id, t.label
FROM cpe_dismantle i
JOIN dismantle_types t ON t.id = i.dismantle_type_id
ORDER BY t.id
"""
