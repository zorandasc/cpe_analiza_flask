from collections import defaultdict
from datetime import timedelta
from sqlalchemy import func, text
from app.extensions import db
from app.models import CpeInventory, CpeDismantle, DismantleTypes, CpeTypes, Cities


# cpe inventory IS EVENT/STATE-CHANGE TABLE
# You only need carry-forward when your table
# stores sparse changes instead of full state.
def get_cpe_inventory_chart_data(city_id=None, cpe_id=None, cpe_type=None, weeks=None):
    """
    # 1. Build weekly timeline (Fridays), we want 5 last weeks
    # 2. Fetch sparse snapshot data from DB, data form db can be missing week
    # SQL returns sparse weekly deltas per type
    # 3. Reconstruct full state per week (carry forward)
    # Python reconstructs full snapshot timeline
    # 4. Format for Chart.js
    # So this code convert:sparse events ➝ full weekly snapshots ➝ totals
    """
    # ---------------------------------------
    # 1. Find min, max available week in all DB
    # ---------------------------------------

    min_week, max_week = db.session.query(
        func.min(CpeInventory.week_end), func.max(CpeInventory.week_end)
    ).one()

    if not max_week:
        return {"labels": [], "datasets": []}

    if weeks:
        # for example: if week 5 , we need to substract 5*7 days
        start_week = max_week - timedelta(days=7 * (weeks - 1))
    else:
        start_week = min_week

    # CONTINUOE TIMELINE OF FRIDAYS
    timeline = build_timeline(start_week, max_week)

    # ---------------------------------------
    # 2. Base query (sparse snapshots) on some week_end there is no data
    # ---------------------------------------
    q = (
        db.session.query(
            CpeInventory.city_id,
            CpeInventory.week_end,
            CpeInventory.cpe_type_id,
            CpeTypes.type,
            CpeInventory.quantity,
        )
        .join(CpeTypes, CpeTypes.id == CpeInventory.cpe_type_id)
        .join(Cities, Cities.id == CpeInventory.city_id)
        .filter(CpeInventory.week_end <= max_week)
        .filter(CpeTypes.visible_in_total)  # only cpe types that are visisble
    )

    if city_id:
        q = q.filter(Cities.id == city_id)
    else:
        # Totat sum by all cities but Without Raspoloziva oprema
        q = q.filter(Cities.include_in_total)

    if cpe_id:
        q = q.filter(CpeInventory.cpe_type_id == cpe_id)

    if cpe_type:
        q = q.filter(CpeTypes.type == cpe_type)

    rows = q.all()

    # ROW IN ROWS- THERE MAY BE MISSING WEEK_ENDS:
    # (3, datetime.date(2026, 1, 9), 7, <CpeTypeEnum.ONT: 'ONT'>, 7)
    # (3, datetime.date(2026, 1, 9), 8, <CpeTypeEnum.ONT: 'ONT'>, 444)
    # for city_id=13, week=5, cpe_type='ONt':
    # print(row, "\n"): 10 rows, 5 for ont nokia 5 for huawei
    if not rows:
        return {"labels": [w.strftime("%d-%m-%Y") for w in timeline], "datasets": []}

    # ---------------------------------------
    # 3. Rebuild weekly state per city/type -DATA GROUPING
    # ---------------------------------------
    # 3.1 create empty state
    state = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    """
    city
    └── cpe_type
      └── week → quantity
    """

    # 3.2 FILL THE STATE WITH VALUES
    for city_id_, week_end, cpe_type_id_, type_key, qty in rows:
        state[city_id_][type_key][week_end] += qty
    """
    #state look like:
    #for city_id=1
    {1: {
       "router": {
           2026-01-23: 100,
           2026-02-06: 120
       },
       "modem": {
           2026-01-23: 50
       }
     },
    #for city_id=2
    2: {
       "router": {
           2026-01-23: 80
       }
     }
    }
    """
    # ---------------------------------------
    # 4. Aggregate into chart datasets
    # ---------------------------------------
    """
    FOR EVERY TIME SLOT SUMED FOR EACH CITY 
    router → [0,0,0,0,0] #one slot per week
    modem  → [0,0,0,0,0] #one slot per week
    # defaultdict to automate the creation of lists so you don't have
    # to check if a key exists before adding data to it.
    # Using lambda: is a shorthand way of saying: "Every time you see a new key,
    # run this little function to generate the starting value.
    """
    totals_by_type = defaultdict(lambda: [0] * len(timeline))

    # FILL totals_by_type USING THE Logic THE CARRY FORWARD LOGIC
    for city_data in state.values():
        # now we are inside one city
        # week_map is actuall list of data from db (weeks, quantities) for that cpe_type and city_id
        # week_map = {2026-01-23: 100,2026-02-06: 120}
        for type_key, week_map in city_data.items():
            # 1. FIND ALL WEEKS THAT ARE BEFORE start_week
            previous_weeks = [w for w in week_map if w < start_week]
            # 2. AND THAN USE QUANTITY FROM LAST WEEK BEFORE start_week
            last_quantity = week_map[max(previous_weeks)] if previous_weeks else 0
            # 3. WHAY? BECAUSE IF THERE IS REAL WEEK in week_map
            # FOR FIRST ITERATION THAN WE HAVE VALUE TO POPULATE

            # FOR FILTER WEEKS=5, i WILL GO FROM 1..5
            for i, w in enumerate(timeline):
                if w in week_map:
                    last_quantity = week_map[w]  # week_map[w] is quantity, w is date
                totals_by_type[type_key][i] += last_quantity

    # totals_by_type give us summary per cities for all cpe_types:
    # router → [180, 180, 200, 200, ...]
    # modem  → [50, 50, 50, 50, ...]

    # ---------------------------------------
    # 4.5 Dynamic Y-axis scaling (ALL datasets)
    # ---------------------------------------
    all_values = []
    for values in totals_by_type.values():
        # extend() takes those individual lists and merges them into one big flat list:
        all_values.extend(values)

    if all_values:
        y_min = min(all_values)
        y_max = max(all_values)

        padding = (y_max - y_min) * 0.1

        if padding == 0:
            padding = 1

        y_min -= padding
        y_max += padding

        y_min = max(0, y_min)  # Don't go below zero
    else:
        y_min, y_max = 0, 1  # Default range if no data exists

    # ---------------------------------------
    # 5. Format output per mode
    # ---------------------------------------

    # MODE 1 — single device
    if cpe_id:
        # only one dataset exists
        # data is already filtered by cpe_id in base query so there is only one list
        # Get the first list of numbers
        """
        totals_by_type.values() #This grabs all the lists inside your dictionary
        iter(...) #This turns that collection into an iterator. An iterator is like 
        a conveyor belt; it doesn't show you everything at once, but it’s ready to 
        give you the "next" item when you ask for it.
        The next() function grabs the very first item from that "conveyor belt."
        1.totals_by_type.values()->dict_values([[180, 180, 200, 200]])
        4. The first element is: [180, 180, 200, 200]
        # ALERNATIVE: list(totals_by_type.values())[0]
        # WITH ITER IT IS SAFER VERSION
        """
        values = next(iter(totals_by_type.values()), [])
        return {
            "labels": [w.strftime("%d-%m-%Y") for w in timeline],
            "datasets": [{"label": "Total", "data": values}],
            "y_min": y_min,
            "y_max": y_max,
        }

    # MODE 2 — single type
    if cpe_type:
        values = totals_by_type.get(cpe_type, [])

        # all devices under that type
        devices = (
            db.session.query(CpeTypes.name, CpeTypes.label)
            .filter(CpeTypes.type == cpe_type, CpeTypes.visible_in_total)
            .distinct()
            .order_by(CpeTypes.name)
            .all()
        )

        # Flatten the list of Row objects into a list of strings
        devices = [cpe.label for cpe in devices]

        return {
            "labels": [w.strftime("%d-%m-%Y") for w in timeline],
            "datasets": [{"label": f"Ukupno ({cpe_type})", "data": values}],
            "devices": devices,
            "y_min": y_min,
            "y_max": y_max,
        }

    # MODE 3 — all types
    datasets = [{"label": k, "data": v} for k, v in totals_by_type.items()]

    return {
        "labels": [w.strftime("%d-%m-%Y") for w in timeline],
        "datasets": datasets,
        "y_min": y_min,
        "y_max": y_max,
    }


# cpe dismantle IS EVENT/STATE-CHANGE TABLE
# You only need carry-forward when your table
# stores sparse changes instead of full state.
def get_cpe_dismantle_chart_data(
    city_id=None, cpe_id=None, cpe_type=None, dismantle_type_id=None, weeks=None
):
    # ---------------------------------------
    # 1. Find min, max available week in DB
    # ---------------------------------------
    min_week, max_week = db.session.query(
        func.min(CpeDismantle.week_end), func.max(CpeDismantle.week_end)
    ).one()

    if not max_week:
        return {"labels": [], "datasets": []}

    if weeks:
        # if week 5 , we need to substract 5*7 days
        start_week = max_week - timedelta(days=7 * (weeks - 1))
    else:
        start_week = min_week

    # continue timeline (fridays) from last week and bellow
    timeline = build_timeline(start_week, max_week)

    # ---------------------------------------
    # 2. Base query (sparse snapshots) on some week_end ther is no data
    # ---------------------------------------
    q = (
        db.session.query(
            CpeDismantle.city_id,
            CpeDismantle.week_end,
            CpeDismantle.cpe_type_id,
            CpeTypes.type,
            CpeDismantle.quantity,
        )
        .join(CpeTypes, CpeTypes.id == CpeDismantle.cpe_type_id)
        .join(Cities, Cities.id == CpeDismantle.city_id)
        .join(DismantleTypes, DismantleTypes.id == CpeDismantle.dismantle_type_id)
        .filter(CpeDismantle.week_end <= max_week)
        .filter(CpeTypes.visible_in_dismantle)
    )

    if city_id:
        q = q.filter(Cities.id == city_id)
    else:
        # Totat sum by all cities but Without Raspoloziva oprema
        q = q.filter(Cities.include_in_total)

    if cpe_id:
        q = q.filter(CpeDismantle.cpe_type_id == cpe_id)
    
    if dismantle_type_id:
        q = q.filter(DismantleTypes.id == dismantle_type_id)

    if cpe_type:
        q = q.filter(CpeTypes.type == cpe_type)

    rows = q.all()

    if not rows:
        return {"labels": [w.strftime("%d-%m-%Y") for w in timeline], "datasets": []}

    # ---------------------------------------
    # 3. Rebuild weekly state per city/type, group data
    # --------------------------------------
    # create empty state
    state = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    # fill the state
    for city_id_, week_end, cpe_type_id_, type_key, qty in rows:
        state[city_id_][type_key][week_end] += qty

    # ---------------------------------------
    # 4. Aggregate into chart datasets USING CARRY FORWARD
    # ---------------------------------------
    # koliko ima timeline toliko napravi praznih slotova
    totals_by_type = defaultdict(lambda: [0] * len(timeline))

    # FILL totals_by_type USING CARRY FORWARD
    for city_data in state.values():
        for type_key, week_map in city_data.items():
            # valuble only if first is missing
            previous_weeks = [w for w in week_map if w < start_week]
            last_quantity = week_map[max(previous_weeks)] if previous_weeks else 0

            # for every date (w) in timeline
            for i, w in enumerate(timeline):
                # check if date exisist in real data week_map
                if w in week_map:
                    # if yes take his quantity, continue
                    last_quantity = week_map[w]
                # if no quantity for this timeslot is last value
                totals_by_type[type_key][i] += last_quantity

    # ---------------------------------------
    # 4.5 Dynamic Y-axis scaling (ALL datasets)
    # ---------------------------------------
    all_values = []
    for values in totals_by_type.values():
        # extend() takes those individual lists and merges them into one big flat list:
        all_values.extend(values)

    if all_values:
        y_min = min(all_values)
        y_max = max(all_values)

        padding = (y_max - y_min) * 0.1

        if padding == 0:
            padding = 1

        y_min -= padding
        y_max += padding

        y_min = max(0, y_min)  # Don't go below zero
    else:
        y_min, y_max = 0, 1  # Default range if no data exists

    # ---------------------------------------
    # 5. Format output per mode
    # ---------------------------------------
    # MODE 1 — single device
    if cpe_id:
        values = next(iter(totals_by_type.values()), [])
        return {
            "labels": [w.strftime("%d-%m-%Y") for w in timeline],
            "datasets": [{"label": "Total", "data": values}],
            "y_min": y_min,
            "y_max": y_max,
        }

    # MODE 2 — single type
    if cpe_type:
        values = totals_by_type.get(cpe_type, [])

        devices = (
            db.session.query(CpeTypes.name, CpeTypes.label)
            .filter(CpeTypes.type == cpe_type, CpeTypes.visible_in_dismantle)
            .distinct()
            .order_by(CpeTypes.name)
            .all()
        )

        # Flatten the list of Row objects into a list of strings
        devices = [cpe.label for cpe in devices]

        return {
            "labels": [w.strftime("%d-%m-%Y") for w in timeline],
            "datasets": [{"label": f"Ukupno ({cpe_type})", "data": values}],
            "devices": devices,
            "y_min": y_min,
            "y_max": y_max,
        }

    # MODE 3 — all types
    datasets = [{"label": k, "data": v} for k, v in totals_by_type.items()]

    return {
        "labels": [w.strftime("%d-%m-%Y") for w in timeline],
        "datasets": datasets,
        "y_min": y_min,
        "y_max": y_max,
    }


# IN HERE I DONT USE CARRY FORWARD LOGIC IN PYTHON.
# WHY? BECAUSE IF THERE IS NO WEEK SQL WILL JUST CONNECT ACROS EXSISTING WEEKS
# stb inventory IS SNAPSHOT TABLE, UPDATE IS HAPPENING ACROSS ALL STBS
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

    labels = [r.week_end.strftime("%d-%m-%Y") for r in rows]
    data = [r.total for r in rows]

    # ---------------------------------------
    # 4.5 Dynamic Y-axis scaling (ALL datasets)
    # ---------------------------------------

    if data:
        y_min = min(data)
        y_max = max(data)

        padding = (y_max - y_min) * 0.1

        if padding == 0:
            padding = 1

        y_min -= padding
        y_max += padding

        y_min = max(0, y_min)  # Don't go below zero
    else:
        y_min, y_max = 0, 1  # Default range if no data exists

    return {
        "labels": labels,
        "datasets": [{"label": "STB Uređaji", "data": data}],
        "y_min": y_min,
        "y_max": y_max,
    }


# iptv users charts (Snapshot tables)
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

    labels = [r.week_end.strftime("%d-%m-%Y") for r in rows]
    data = [r.total for r in rows]

    # ---------------------------------------
    # 4.5 Dynamic Y-axis scaling (ALL datasets)
    # ---------------------------------------

    if data:
        y_min = min(data)
        y_max = max(data)

        padding = (y_max - y_min) * 0.1

        if padding == 0:
            padding = 1

        y_min -= padding
        y_max += padding

        y_min = max(0, y_min)  # Don't go below zero
    else:
        y_min, y_max = 0, 1  # Default range if no data exists

    return {
        "labels": labels,
        "datasets": [{"label": "IPTV korisnici", "data": data}],
        "y_min": y_min,
        "y_max": y_max,
    }


# ont inventory (Snapshot tables)
# IN HERE I DONT USE CARRY FORWARD LOGIC IN PYTHON.
# WHY? BECAUSE IF THERE IS NO WEEK SQL WILL JUST CONNECT ACROS EXSISTING WEEKS
# stb inventory IS SNAPSHOT TABLE, UPDATE IS HAPPENING ACROSS ALL CITIES
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

    labels = [r.month_end.strftime("%d-%m-%Y") for r in rows]
    data = [r.total for r in rows]

    # ---------------------------------------
    # 4.5 Dynamic Y-axis scaling (ALL datasets)
    # ---------------------------------------

    if data:
        y_min = min(data)
        y_max = max(data)

        padding = (y_max - y_min) * 0.1

        if padding == 0:
            padding = 1

        y_min -= padding
        y_max += padding
    else:
        y_min, y_max = 0, 1

    return {
        "labels": labels,
        "datasets": [{"label": "ONT uređaji", "data": data}],
        "y_min": y_min,
        "y_max": y_max,
    }


# -----------------
# HELPERS FUNCTIONS
# -----------------


def build_timeline(start_week, max_week):
    """
    Build continuous set of fridays from start_week to max_week
    """
    timeline = []
    current_week = start_week

    while current_week <= max_week:
        timeline.append(current_week)
        current_week += timedelta(days=7)

    return timeline


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
        "cols": "j.id, j.name",  # what is returnet
        "order_by": "j.name",
    },
    "cpe_type": {
        "table": "cpe_types",
        "pk": "id",
        "cols": "j.id, j.label",  # what is returnet
        "order_by": "j.label",
    },
    "stb_type": {
        "table": "stb_types",
        "pk": "id",
        "cols": "j.id, j.label",  # what is returnet
        "order_by": "j.label",
    },
    "dis_type": {
        "table": "dismantle_types",
        "pk": "id",
        "cols": "j.id, j.label",  # what is returnet
        "order_by": "j.label",
    },
}


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


# FOR FILTERS IN CHARTS
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
