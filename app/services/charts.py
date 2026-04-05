from collections import defaultdict
from dateutil.relativedelta import relativedelta
from datetime import timedelta
from sqlalchemy import func, text
from app.extensions import db
from app.models import (
    CpeInventory,
    CpeDismantle,
    CpeBroken,
    AccessInventory,
    DismantleTypes,
    CpeTypes,
    AccessTypes,
    Cities,
    CityVisibilitySettings,
)


# cpe inventory IS EVENT/STATE-CHANGE TABLE
def get_cpe_inventory_chart_data(
    city_id=None, cpe_id=None, cpe_type=None, weeks=None, include_children=False
):
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
    # 2. Base query (sparse snapshots) on some week_end there is no data
    # ---------------------------------------
    base = (
        db.session.query(
            CpeInventory.city_id,
            CpeInventory.week_end,
            CpeInventory.cpe_type_id,
            CpeTypes.type,
            CpeInventory.quantity,
        )
        .join(CpeTypes, CpeTypes.id == CpeInventory.cpe_type_id)
        .join(Cities, Cities.id == CpeInventory.city_id)
        .join(
            CityVisibilitySettings,
            (CityVisibilitySettings.city_id == Cities.id)
            & (CityVisibilitySettings.dataset_key == "cpe_inventory"),
        )
        .filter(CpeTypes.visible_in_total)  # only cpe types that are visisble
        .filter(CityVisibilitySettings.is_visible)
    )

    if city_id:
        selected_city = db.session.get(Cities, city_id)

        if include_children and selected_city and selected_city.parent_city_id is None:
            # Parent WITH ALL children
            city_ids = [city_id] + [
                c.id
                for c in db.session.query(Cities.id)
                .filter(Cities.parent_city_id == city_id)
                .all()
            ]
            base = base.filter(CpeInventory.city_id.in_(city_ids))
        else:
            # Standalone city (parent OR child)
            base = base.filter(Cities.id == city_id)

    else:
        #  All cities but Without Raspoloziva oprema
        base = base.filter(CityVisibilitySettings.included_in_total_sum)

    if cpe_id:
        base = base.filter(CpeInventory.cpe_type_id == cpe_id)

    if cpe_type:
        base = base.filter(CpeTypes.type == cpe_type)

    # ---------------------------------------
    # 1. Find min, max available week in all DB
    # ---------------------------------------
    min_week, max_week = base.with_entities(
        func.min(CpeInventory.week_end), func.max(CpeInventory.week_end)
    ).one()

    if not max_week:
        return {"labels": [], "datasets": []}

    # CONTINUOE TIMELINE OF FRIDAYS
    timeline = build_week_timeline(weeks, min_week, max_week)

    # 1. SQL: Group by City and Week
    base_agg = base.with_entities(
        CpeInventory.city_id,
        CpeInventory.week_end,
        CpeTypes.type.label("type_key"),
        func.sum(CpeInventory.quantity).label("total_qty"),
    ).group_by(CpeInventory.city_id, CpeInventory.week_end, CpeTypes.type)

    # EVERY ROW IS (city_id, week_end, cpe_types, sum(qty))
    # ROW IN ROWS- THERE MAY BE MISSING WEEK_ENDS:
    rows = base_agg.all()

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
    for city_id_, week_end, type_key, qty in rows:
        state[city_id_][type_key][week_end] = qty
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
    # 4. Aggregate into chart datasets USING CARRY FORWARD/LINEAR FOR MISSING WEEK
    # ---------------------------------------
    """
    # defaultdict to automate the creation of lists so you don't have
    # to check if a key exists before adding data to it.
    # Using lambda: is a shorthand way of saying: "Every time you see a new key,
    # run this little function to generate the starting value.
    """
    totals_by_type = defaultdict(lambda: [0] * len(timeline))

    # FOR EVERY CITY
    for city_id, city_data in state.items():
        for type_key, week_map in city_data.items():
            # This keeps the 'Line' steady for each city individually
            series = interpolate_series(timeline, week_map, method="linear")
            for i, val in enumerate(series):
                totals_by_type[type_key][i] += val
    """   
    totals_by_type: FOR EVERY CPE-TYPE MAKE len(timeline) TIME SLOTS 
    router → [0,0,0,0,0] #one slot per week
    modem  → [0,0,0,0,0] #one slot per week
    """

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
def get_cpe_dismantle_chart_data(
    city_id=None,
    cpe_id=None,
    cpe_type=None,
    dismantle_type_id=None,
    weeks=None,
    include_children=False,
):

    # ---------------------------------------
    # 1. Base query (sparse snapshots) on some week_end ther is no data
    # ---------------------------------------
    base = (
        db.session.query(
            CpeDismantle.city_id,
            CpeDismantle.week_end,
            CpeDismantle.cpe_type_id,
            CpeTypes.type,
            CpeDismantle.quantity,
        )
        .join(CpeTypes, CpeTypes.id == CpeDismantle.cpe_type_id)
        .join(Cities, Cities.id == CpeDismantle.city_id)
        .join(
            CityVisibilitySettings,
            (CityVisibilitySettings.city_id == Cities.id)
            & (CityVisibilitySettings.dataset_key == "cpe_dismantle"),
        )
        .join(DismantleTypes, DismantleTypes.id == CpeDismantle.dismantle_type_id)
        .filter(CpeTypes.visible_in_dismantle)
        .filter(CityVisibilitySettings.is_visible)
    )

    if city_id:
        selected_city = db.session.get(Cities, city_id)

        if include_children and selected_city and selected_city.parent_city_id is None:
            # Parent CITY WITH ALL children
            city_ids = [city_id] + [
                c.id
                for c in db.session.query(Cities.id)
                .filter(Cities.parent_city_id == city_id)
                .all()
            ]
            base = base.filter(CpeDismantle.city_id.in_(city_ids))
        else:
            # Standalone city (parent OR child)
            base = base.filter(Cities.id == city_id)
    else:
        # All cities but Without Raspoloziva oprema
        base = base.filter(CityVisibilitySettings.included_in_total_sum)

    if cpe_id:
        base = base.filter(CpeDismantle.cpe_type_id == cpe_id)

    if dismantle_type_id:
        base = base.filter(DismantleTypes.id == dismantle_type_id)

    if cpe_type:
        base = base.filter(CpeTypes.type == cpe_type)

    # ---------------------------------------
    # 2. Find min, max available week in DB
    # ---------------------------------------
    # with_entities PICK THOSE COLUMNS FROM base QUERRY/TABLE
    min_week, max_week = base.with_entities(
        func.min(CpeDismantle.week_end), func.max(CpeDismantle.week_end)
    ).one()

    if not max_week:
        return {"labels": [], "datasets": []}

    # CONTINUOE TIMELINE OF FRIDAYS
    timeline = build_week_timeline(weeks, min_week, max_week)

    # 1. SQL: Group by City and Week
    base_agg = base.with_entities(
        CpeDismantle.city_id,
        CpeDismantle.week_end,
        CpeTypes.type.label("type_key"),
        func.sum(CpeDismantle.quantity).label("total_qty"),
    ).group_by(CpeDismantle.city_id, CpeDismantle.week_end, CpeTypes.type)

    # EVERY ROW IS (city_id, week_end, cpe_types, sum(qty))
    rows = base_agg.all()

    if not rows:
        return {"labels": [w.strftime("%d-%m-%Y") for w in timeline], "datasets": []}

    # ---------------------------------------
    # 3. Rebuild weekly state per city/type, group data into dictonary
    # --------------------------------------
    # 2. Python: Create the state, but ONLY for the cities that have data
    state = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for city_id_, week_end, type_key, qty in rows:
        state[city_id_][type_key][week_end] = qty

    # ---------------------------------------
    # 4. Aggregate into chart datasets USING CARRY FORWARD/LINEAR FOR MISSING WEEK
    # ---------------------------------------
    totals_by_type = defaultdict(lambda: [0] * len(timeline))

    # FOR EVERY CITY
    for city_id, city_data in state.items():
        for type_key, week_map in city_data.items():
            # This keeps the 'Line' steady for each city individually
            series = interpolate_series(timeline, week_map, method="linear")
            for i, val in enumerate(series):
                totals_by_type[type_key][i] += val

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


# cpe inventory IS EVENT/STATE-CHANGE TABLE
def get_cpe_broken_chart_data(
    city_id=None, cpe_id=None, cpe_type=None, weeks=None, include_children=False
):

    # ---------------------------------------
    # 1. Base query (sparse snapshots) on some week_end there is no data
    # ---------------------------------------
    base = (
        db.session.query(
            CpeBroken.city_id,
            CpeBroken.week_end,
            CpeBroken.cpe_type_id,
            CpeTypes.type,
            CpeBroken.quantity,
        )
        .join(CpeTypes, CpeTypes.id == CpeBroken.cpe_type_id)
        .join(Cities, Cities.id == CpeBroken.city_id)
        .join(
            CityVisibilitySettings,
            (CityVisibilitySettings.city_id == Cities.id)
            & (CityVisibilitySettings.dataset_key == "cpe_broken"),
        )
        .filter(CpeTypes.visible_in_broken)  # only cpe types that are visisble
        .filter(CityVisibilitySettings.is_visible)
    )

    if city_id:
        selected_city = db.session.get(Cities, city_id)

        if include_children and selected_city and selected_city.parent_city_id is None:
            # Parent WITH all children
            city_ids = [city_id] + [
                c.id
                for c in db.session.query(Cities.id)
                .filter(Cities.parent_city_id == city_id)
                .all()
            ]
            base = base.filter(CpeBroken.city_id.in_(city_ids))
        else:
            # Standalone city (parent OR child)
            base = base.filter(Cities.id == city_id)
    else:
        #  All cities but Without Raspoloziva oprema
        base = base.filter(CityVisibilitySettings.included_in_total_sum)

    if cpe_id:
        base = base.filter(CpeBroken.cpe_type_id == cpe_id)

    if cpe_type:
        base = base.filter(CpeTypes.type == cpe_type)

    # ---------------------------------------
    # 2. Find min, max available week in all DB
    # ---------------------------------------
    min_week, max_week = base.with_entities(
        func.min(CpeBroken.week_end), func.max(CpeBroken.week_end)
    ).one()

    if not max_week:
        return {"labels": [], "datasets": []}

    # CONTINUOE TIMELINE OF FRIDAYS
    timeline = build_week_timeline(weeks, min_week, max_week)

    # 1. SQL: Group by City and Week
    base_agg = base.with_entities(
        CpeBroken.city_id,
        CpeBroken.week_end,
        CpeTypes.type.label("type_key"),
        func.sum(CpeBroken.quantity).label("total_qty"),
    ).group_by(CpeBroken.city_id, CpeBroken.week_end, CpeTypes.type)

    # EVERY ROW IS (city_id, week_end, cpe_types, sum(qty))
    rows = base_agg.all()

    if not rows:
        return {"labels": [w.strftime("%d-%m-%Y") for w in timeline], "datasets": []}

    # ---------------------------------------
    # 3. Rebuild weekly state per city/type -DATA GROUPING
    # ---------------------------------------
    # Python: Create the state, but ONLY for the cities that have data
    state = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for city_id_, week_end, type_key, qty in rows:
        state[city_id_][type_key][week_end] = qty

    # ---------------------------------------
    # 4. Aggregate into chart datasets
    # ---------------------------------------

    totals_by_type = defaultdict(lambda: [0] * len(timeline))

    for city_id, city_data in state.items():
        for type_key, week_map in city_data.items():
            # This keeps the 'Line' steady for each city individually
            series = interpolate_series(timeline, week_map, method="linear")
            for i, val in enumerate(series):
                totals_by_type[type_key][i] += val

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


def get_stb_inventory_chart_data(stb_type_id=None, weeks=None):

    params = {}
    where = ""

    if stb_type_id:
        where = "AND stb_type_id = :stb_type_id"
        params["stb_type_id"] = stb_type_id

    sql = f"""
        SELECT week_end, SUM(quantity) AS total
        FROM stb_inventory
        WHERE 1=1 {where}
        GROUP BY week_end
        ORDER BY week_end
    """

    rows = db.session.execute(text(sql), params).fetchall()

    if not rows:
        return {"labels": [], "datasets": []}

    week_map = {r.week_end: r.total for r in rows}

    min_week = min(week_map.keys())
    max_week = max(week_map.keys())

    timeline = build_week_timeline(weeks, min_week, max_week)

    series = interpolate_series(
        timeline,
        week_map,
        method="linear",
    )

    labels = [w.strftime("%d-%m-%Y") for w in timeline]
    data = [s for s in series]

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


def get_iptv_inventory_chart_data(weeks=None):

    sql = """
            SELECT week_end, SUM(total_users) AS total
            FROM iptv_users
            GROUP BY week_end
            ORDER BY week_end
        """

    rows = db.session.execute(text(sql)).fetchall()

    week_map = {r.week_end: r.total for r in rows}

    min_week = min(week_map.keys())
    max_week = max(week_map.keys())

    timeline = build_week_timeline(weeks, min_week, max_week)

    series = interpolate_series(
        timeline,
        week_map,
        method="linear",
    )

    labels = [w.strftime("%d-%m-%Y") for w in timeline]
    data = [s for s in series]

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


def get_access_inventory_chart_data(access_id=None, city_id=None, months=None):

    # ---------------------------------------
    # 1. Base query (sparse snapshots) on some month_end there is no data
    # ---------------------------------------
    base = (
        db.session.query(
            AccessInventory.city_id,
            AccessInventory.month_end,
            AccessInventory.access_type_id,
            AccessTypes.name,
            AccessInventory.quantity,
        )
        .join(AccessTypes, AccessTypes.id == AccessInventory.access_type_id)
        .join(Cities, Cities.id == AccessInventory.city_id)
        .join(
            CityVisibilitySettings,
            (CityVisibilitySettings.city_id == Cities.id)
            & (CityVisibilitySettings.dataset_key == "access_inventory"),
        )
        .filter(AccessTypes.is_active)
        .filter(CityVisibilitySettings.is_visible)
    )

    if access_id:
        base = base.filter(AccessTypes.id == access_id)
    if city_id:
        base = base.filter(Cities.id == city_id)
    else:
        # Totat sum by all cities but Without Raspoloziva oprema
        base = base.filter(CityVisibilitySettings.included_in_total_sum)

    # ---------------------------------------
    # 2. Find min, max available month in DB from filtered data
    # ---------------------------------------
    min_month, max_month = base.with_entities(
        func.min(AccessInventory.month_end), func.max(AccessInventory.month_end)
    ).one()

    if not max_month:
        return {"labels": [], "datasets": []}

    # BUILD CONTINUOUS TIMELINE OF MONTHS
    timeline = build_month_timeline(months, min_month, max_month)

     # 1. SQL: Group by City and Week
    base_agg = base.with_entities(
        AccessInventory.city_id,
        AccessInventory.month_end,
        AccessTypes.name.label("type_key"),
        func.sum(AccessInventory.quantity).label("total_qty"),
    ).group_by(AccessInventory.city_id, AccessInventory.month_end, AccessTypes.name)

    # EVERY ROW IS (city_id, month_end, acces_types, sum(qty))
    # ROW IN ROWS- THERE MAY BE MISSING WEEK_ENDS:
    rows = base_agg.all()

    if not rows:
        return {"labels": [w.strftime("%d-%m-%Y") for w in timeline], "datasets": []}

    # ---------------------------------------
    # 3. Rebuild weekly state per city/type, group data
    # --------------------------------------
    # create empty state
    state = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    # fill the state
    for city_id_, month_end, type_key, qty in rows:
        state[city_id_][type_key][month_end] = qty

    # ---------------------------------------
    # 4. Aggregate into chart datasets USING CARRY FORWARD
    # ---------------------------------------
    totals_by_type = defaultdict(lambda: [0] * len(timeline))

    # FOR EVERY CITY
    for city_id, city_data in state.items():
        for type_key, month_map in city_data.items():
            # This keeps the 'Line' steady for each city individually
            series = interpolate_series(timeline, month_map, method="linear")
            for i, val in enumerate(series):
                totals_by_type[type_key][i] += val

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
    # 5. Format output
    # ---------------------------------------
    # MODE 1 — single device
    if access_id:
        values = list(totals_by_type.values())[0]
        return {
            "labels": [w.strftime("%d-%m-%Y") for w in timeline],
            "datasets": [{"label": "Total", "data": values}],
            "y_min": y_min,
            "y_max": y_max,
        }

    datasets = [{"label": k, "data": v} for k, v in totals_by_type.items()]

    return {
        "labels": [w.strftime("%d-%m-%Y") for w in timeline],
        "datasets": datasets,
        "y_min": y_min,
        "y_max": y_max,
    }


# -----------------
# HELPERS FUNCTIONS
# -----------------
def build_week_timeline(weeks, min_week, max_week):
    """
    Build continuous set of fridays from start_week to max_week
    """
    if not max_week:
        return [], None

    if weeks:
        # for example: if week 5 , we need to substract 5*7 days
        start_week = max_week - timedelta(days=7 * (weeks - 1))
    else:
        start_week = min_week

    timeline = []
    current_week = start_week

    while current_week <= max_week:
        timeline.append(current_week)
        current_week += timedelta(days=7)

    return timeline


def build_month_timeline(months, min_month, max_month):
    """
    Returns:
        timeline: list[date] (continuous month_end dates)
        start_month: date
    """

    if not max_month:
        return [], None

    if months:
        # Go back N-1 months from the max_month
        start_month = max_month - relativedelta(months=months - 1)

        # Don't allow start before actual data
        if min_month and start_month < min_month:
            start_month = min_month
    else:
        start_month = min_month

    # 2. Ensure the first date in the timeline is the LAST day of its month
    current = start_month + relativedelta(day=31)

    timeline = []

    while current <= max_month:
        timeline.append(current)

        # Move to the last day of the next month in one clean step
        current = current + relativedelta(months=1, day=31)

    return timeline


def get_visible_cities(dataset_key):
    return db.session.execute(
        text("""
            SELECT c.id, c.name, c.parent_city_id
            FROM cities c
            
            JOIN city_visibility_settings s
              ON s.city_id = c.id
             AND s.dataset_key = :dataset_key

            WHERE s.is_visible = true
            
            ORDER BY c.id
            """),
        {"dataset_key": dataset_key},
    ).fetchall()


# LINEAR AND CARRY FORWARD APROXIMATION OF MISSING DATA
def interpolate_series(timeline, week_map, method="locf"):

    # timeline - continouse timeline
    # week_map - data/weeks from db
    # week_map is actuall list of all data from db (weeks, quantities) for that cpe_type and city_id
    # week_map = {2026-01-23: 100, 2026-02-06: 120}
    # linear - y=y1​+(x2​−x1​)(x−x1​)​(y2​−y1​)

    sorted_weeks = sorted(week_map.keys())
    result = []

    for w in timeline:
        if w in week_map:
            result.append(week_map[w])
            # IF ALL DATA IN TIMELINE AND IN DB THAT IS IT, FINISH
            continue

        # IF QUNTIY MISSING ON SOME WEEKS IN DB THAN APROXIMATE
        if method == "locf":  # CARRY FORWARD
            prev = next((pw for pw in reversed(sorted_weeks) if pw < w), None)
            result.append(week_map[prev] if prev else 0)

        elif method == "linear":  # LINEAR
            prev = next((pw for pw in reversed(sorted_weeks) if pw < w), None)
            next_ = next((nw for nw in sorted_weeks if nw > w), None)

            if prev and next_:
                y1 = week_map[prev]
                y2 = week_map[next_]

                ratio = (w - prev).days / (next_ - prev).days
                result.append(int(round(y1 + ratio * (y2 - y1))))

            elif prev:
                result.append(week_map[prev])
            elif next_:
                result.append(week_map[next_])
            else:
                result.append(0)

    return result
