def get_cpe_inventory_chart_data(city_id=None, cpe_id=None, cpe_type=None, weeks=None):

    # ---------------------------------------
    # 1. Base query (sparse snapshots) on some week_end there is no data
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
        .filter(CpeTypes.visible_in_total)  # only cpe types that are visisble
    )

    if city_id:
        base = base.filter(Cities.id == city_id)
    else:
        # Totat sum by all cities but Without Raspoloziva oprema
        base = base.filter(Cities.include_in_total)

    if cpe_id:
        base = base.filter(CpeInventory.cpe_type_id == cpe_id)

    if cpe_type:
        base = base.filter(CpeTypes.type == cpe_type)

    # ---------------------------------------
    # 2. Find min, max available week in all DB
    # ---------------------------------------
    min_week, max_week = base.with_entities(
        func.min(CpeInventory.week_end), func.max(CpeInventory.week_end)
    ).one()

    if not max_week:
        return {"labels": [], "datasets": []}

    # CONTINUOE TIMELINE OF FRIDAYS
    timeline, start_week = build_week_timeline(weeks, min_week, max_week)

    rows = base.all()

    if not rows:
        return {"labels": [w.strftime("%d-%m-%Y") for w in timeline], "datasets": []}

    # ---------------------------------------
    # 3. Rebuild weekly state per city/type -DATA GROUPING
    # ---------------------------------------
    # 3.1 create empty state
    state = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    # 3.2 FILL THE STATE WITH VALUES
    for city_id_, week_end, cpe_type_id_, type_key, qty in rows:
        state[city_id_][type_key][week_end] += qty

    # ---------------------------------------
    # 4. Aggregate into chart datasets
    # ---------------------------------------
    totals_by_type = defaultdict(lambda: [0] * len(timeline))

    # FILL totals_by_type USING THE Logic THE CARRY FORWARD LOGIC
    for city_data in state.values():
   
        for type_key, week_map in city_data.items():
            # week_map are all data from db query
            sorted_weeks = sorted(week_map.keys())
            last_quantity = 0

            for w in sorted_weeks:
                if w < start_week:
                    last_quantity = week_map[w]
                else:
                    break

            # FOR FILTER WEEKS=5, i WILL GO FROM 1..5
            for i, w in enumerate(timeline):
                # check if date exisist in real data week_map
                if w in week_map:
                    # if yes take his quantity, continue
                    # week_map[w] is quantity, w is date
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

