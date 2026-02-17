def get_cpe_inventory_chart_data(city_id=None, cpe_id=None, cpe_type=None, weeks=None):
   
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

    # continue timeline (fridays) from last week and bellow
    timeline = build_timeline(start_week, max_week)

    # ---------------------------------------
    # 2. Base query (sparse snapshots) on some week_end ther is no data
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
        .filter(
            CpeInventory.week_end >= start_week,
            CpeInventory.week_end <= max_week,
        )
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

    if not rows:
        return {"labels": [w.strftime("%d-%m-%Y") for w in timeline], "datasets": []}

    # ---------------------------------------
    # 3. Rebuild weekly state per city/type
    # ---------------------------------------
    # create empty state
    state = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
   
    for city_id_, week_end, cpe_type_id_, type_key, qty in rows:
        state[city_id_][type_key][week_end] += qty

    # ---------------------------------------
    # 4. Aggregate into chart datasets
    # ---------------------------------------

    # define totals_by_type
    totals_by_type = defaultdict(lambda: [0] * len(timeline))

    # fill totals_by_type using "Carry Forward" Logic
    for city_data in state.values():
    
        for type_key, week_map in city_data.items():
            # now we are inside one cpe_type
            # The "Carry Forward" Logic
            last = 0
            # FOR FILTER WEEKS=5, i WILL GO FROM 1..5
            for i, w in enumerate(timeline):
                if w in week_map:
                    last = week_map[w]
                totals_by_type[type_key][i] += last

  

    # ---------------------------------------
    # 5. Format output per mode
    # ---------------------------------------
    # MODE 1 — single device
    if cpe_id:
      
        values = next(iter(totals_by_type.values()), [])
        return {
            "labels": [w.strftime("%d-%m-%Y") for w in timeline],
            "datasets": [{"label": "Total", "data": values}],
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
            "mode": "type-total",
        }

    # MODE 3 — all types
    datasets = [{"label": k, "data": v} for k, v in totals_by_type.items()]

    return {
        "labels": [w.strftime("%d-%m-%Y") for w in timeline],
        "datasets": datasets,
    }