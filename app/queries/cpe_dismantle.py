from sqlalchemy import text
from app.extensions import db
from datetime import datetime
from app.utils.simplepagination import SimplePagination


def get_cpe_dismantle_pivoted(
    schema_list: list, week_end: datetime.date, group_name: str
):
    if not schema_list:
        # Return empty data lists immediately if no active CPE types are found
        return []

    case_columns = []
    sum_columns = []

    params = {"week_end": week_end, "group_name": group_name}

    for i, model in enumerate(schema_list):
        place_holder = f"cpe_{i}"

        case_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN cpe_name = :{place_holder} THEN quantity END),
                0
            ) AS "{model["name"]}"
            """
        )
        sum_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN cpe_name = :{place_holder} THEN quantity END),
                0
            ) AS "{model["name"]}"
            """
        )
        params[place_holder] = model["name"]

    SQL_QUERY = f"""
        -- ✅ FASTEST WAY TO GET LATEST ROW PER GROUP (The Latest Filter) -CTE
        WITH ranked_dismantle AS (
            SELECT DISTINCT ON (city_id, cpe_type_id, dismantle_type_id)
                city_id, cpe_type_id, dismantle_type_id, quantity, week_end
            FROM cpe_dismantle
            WHERE week_end <= :week_end
            ORDER BY city_id, cpe_type_id, dismantle_type_id, week_end DESC
        ),

        -- The Enrichment Center -CTE
        filtered_data AS (
            SELECT
                c.id AS city_id,
                COALESCE(c.parent_city_id, c.id) AS major_city_id,
                mc.name AS city_name,
                s.included_in_total_sum AS include_in_total,

                rd.cpe_type_id,
                ct.name AS cpe_name,

                dt.id AS dismantle_type_id,
                dt.code AS dismantle_code,
                dt.group_name, -- This is the column in your dismantle_types table

                COALESCE(rd.quantity, 0) AS quantity

            FROM cities c
        
            JOIN city_visibility_settings s 
                ON s.city_id = c.id AND s.dataset_key = 'cpe_dismantle'

            LEFT JOIN cities mc 
                ON mc.id = COALESCE(c.parent_city_id, c.id)

        
            -- Join against our pre-filtered 'latest' records -(Join with CTE)
            LEFT JOIN ranked_dismantle rd 
                ON rd.city_id = c.id

            LEFT JOIN dismantle_types dt 
                ON dt.id = rd.dismantle_type_id

            LEFT JOIN cpe_types ct 
                ON ct.id = rd.cpe_type_id

            WHERE s.is_visible = true AND dt.group_name = :group_name -- <--- THE CONNECTION POINT BETWEEN PASSED group_name AND COLUMN group_name
        ),

        -- ✅ CITY/WEEK_END/GROUP STATUS -CTE
        -- carry-forward updated_at
       city_status AS (
            SELECT DISTINCT ON (city_id)
                city_id, updated_at
            FROM dismantle_city_week_update
            WHERE week_end <= :week_end AND group_name = :group_name
            ORDER BY city_id, week_end DESC
            ),

        -- ✅ SUBCITY COUNT CTE
        subcity_counts AS (
            SELECT
                parent_city_id AS major_city_id,
                COUNT(*) AS subcity_count
            FROM cities c
            JOIN city_visibility_settings s 
                ON s.city_id = c.id AND s.dataset_key = 'cpe_dismantle'
            WHERE parent_city_id IS NOT NULL AND s.is_visible = true
            GROUP BY parent_city_id
        )

        -- ✅ MAIN RESULT (MAJOR CITIES)
        SELECT
            fd.major_city_id AS city_id,
            fd.city_name,
            COALESCE(sc.subcity_count, 0) AS subcity_count,
            fd.dismantle_type_id,
            fd.dismantle_code,
            {", ".join(case_columns)},
            -- Parent shows oldest update of its sub-entities
            CASE 
                -- If the count of rows is greater than the count of actual timestamps, 
                -- it means at least one subcity is NULL. Force the whole thing to NULL.
                WHEN COUNT(*) > COUNT(cs.updated_at) THEN NULL 
                -- Otherwise, everyone has a timestamp, so take the oldest one.
                ELSE MIN(cs.updated_at) 
            END AS updated_at

        FROM filtered_data fd

        LEFT JOIN subcity_counts sc ON sc.major_city_id = fd.major_city_id

        LEFT JOIN city_status cs ON cs.city_id = fd.city_id

        GROUP BY fd.major_city_id, fd.city_name, sc.subcity_count, fd.dismantle_type_id, fd.dismantle_code

        UNION ALL

        -- ✅ TOTAL ROW
        SELECT
            NULL, 'UKUPNO', NULL, dismantle_type_id, dismantle_code,
            {", ".join(sum_columns)},
            NULL
        FROM filtered_data
        WHERE include_in_total = true
        GROUP BY dismantle_type_id, dismantle_code
        ORDER BY city_id, dismantle_type_id NULLS LAST;
        """
    result = db.session.execute(text(SQL_QUERY), params)

    return [row._asdict() for row in result.all()]


def get_cpe_dismantle_subcities(
    schema_list: list, week_end: datetime.date, major_city_id: int, group_name: str
):
    """
    Retrieves the records for sub city for a specific major_city_id, pivoted by CPE type.
    This query handles pagination internally based on the unique WEEK_END timestamp.
    """
    if not schema_list:
        # Return empty data lists immediately if no active CPE types are found
        return []

    case_columns = []
    sum_columns = []

    params = {
        "major_city_id": major_city_id,
        "week_end": week_end,
        "group_name": group_name,
    }

    for i, model in enumerate(schema_list):
        place_holder = f"cpe_{i}"

        case_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN cpe_name = :{place_holder} THEN quantity END),
                0
            ) AS "{model["name"]}"
            """
        )
        sum_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN cpe_name = :{place_holder} THEN quantity END),
                0
            ) AS "{model["name"]}"
            """
        )
        params[place_holder] = model["name"]

    SQL_QUERY = f"""
        -- ✅ Carry-forward quantity data
        WITH ranked_dismantle AS (
            SELECT DISTINCT ON (city_id, cpe_type_id, dismantle_type_id)
                city_id, cpe_type_id, dismantle_type_id, quantity
            FROM cpe_dismantle
            WHERE week_end <= :week_end
            ORDER BY city_id, cpe_type_id, dismantle_type_id, week_end DESC
        ),

        -- ✅ Filter cities for this specific view (Major + its children)
        filtered_data AS (
            SELECT
                c.id AS city_id,
                c.name AS city_name,
                s.included_in_total_sum AS include_in_total,

                rd.cpe_type_id,
                ct.name AS cpe_name,

                dt.id AS dismantle_type_id,
                dt.code AS dismantle_code,
                rd.quantity
                
            FROM cities c

            JOIN city_visibility_settings s
                ON s.city_id = c.id AND s.dataset_key = 'cpe_dismantle'

            LEFT JOIN ranked_dismantle rd 
                ON rd.city_id = c.id

            LEFT JOIN dismantle_types dt
                ON dt.id = rd.dismantle_type_id

            LEFT JOIN cpe_types ct 
                ON ct.id = rd.cpe_type_id

            WHERE (c.id = :major_city_id OR c.parent_city_id = :major_city_id)
              AND s.is_visible = true
              AND dt.group_name = :group_name
        ),

        -- ✅ Pull updated status from helper table
        city_status AS (
            SELECT DISTINCT ON (city_id)
                city_id, updated_at
            FROM dismantle_city_week_update
            WHERE week_end <= :week_end 
              AND group_name = :group_name
            ORDER BY city_id, week_end DESC
        )

        -- ✅ MAIN RESULT
        SELECT
            fd.city_id,
            fd.city_name,
            fd.dismantle_type_id,
            fd.dismantle_code,
            {", ".join(case_columns)},
            cs.updated_at
        FROM filtered_data fd
        LEFT JOIN city_status cs ON cs.city_id = fd.city_id
        GROUP BY 
            fd.city_id, fd.city_name, fd.dismantle_type_id, fd.dismantle_code, cs.updated_at

        UNION ALL

        -- ✅ TOTAL ROW
        SELECT
            NULL AS city_id,
            'UKUPNO' AS city_name,
            dismantle_type_id,
            dismantle_code,
            {", ".join(sum_columns)},
            NULL AS updated_at
        FROM filtered_data
        WHERE include_in_total = true
        GROUP BY dismantle_type_id, dismantle_code

        ORDER BY city_id, dismantle_type_id NULLS LAST;
    """

    result = db.session.execute(text(SQL_QUERY), params)

    return [row._asdict() for row in result.all()]


def get_cpe_dismantle_city_history(
    city_id: int,
    scope: str,
    schema_list: list,
    list_of_dismantles: list,
    page: int,
    per_page: int,
):
    """
    Retrieves the historical records for a specific city_id, pivoted by CPE type.
    This query handles pagination internally based on the unique WEEK_END timestamp.

    scope = "city"   → history for one city
    scope = "major"  → history for major city + all its subcities
    """
    if not schema_list:
        # Return empty data lists immediately if no active CPE types are found
        return []

    if scope == "major":
        city_filter = """
            cd.city_id IN (
                SELECT id
                FROM cities
                WHERE id = :city_id
                OR parent_city_id = :city_id
            )
            """
    else:
        city_filter = "cd.city_id = :city_id"

    # We need a separate query to get the total count for pagination
    count_query = text(
        f"""
            SELECT COUNT(DISTINCT cd.week_end)
            FROM cpe_dismantle cd
            WHERE {city_filter}
            AND cd.dismantle_type_id IN :d_list
        """
    )

    total_count = db.session.execute(
        count_query,
        {
            "city_id": city_id,
            "d_list": tuple(list_of_dismantles),
        },
    ).scalar()

    # Calculate offset
    offset = (page - 1) * per_page

    # case_columns is actualy at building list of sql statements:
    # [SUM(CASE WHEN ct.id = :{place_holder} THEN cd.quantity END), ....]
    case_columns = []

    params = {
        "city_id": city_id,
        "limit": per_page,
        "offset": offset,
        "d_list": tuple(list_of_dismantles),
    }

    for i, model in enumerate(schema_list):
        place_holder = f"cpe_{i}"
        # build list of sql statement with parameterized values
        # this statement with injected values will be exsecutet at the end
        # with result = db.session.execute(text(SQL_QUERY), params)
        case_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN ct.id = :{place_holder} THEN cd.quantity END),
                0
            ) AS "{model["name"]}"
            """
        )
        # this will fill params object with: cpe_1= model[1], cpe_2=model[2],..
        params[place_holder] = model["id"]

    SQL_QUERY = f"""
        -- 1. Get paginated weeks (LIMIT, OFFSET)
        WITH weeks AS (
            SELECT DISTINCT cd.week_end
            FROM cpe_dismantle cd
            WHERE {city_filter}
            AND cd.dismantle_type_id IN :d_list
            ORDER BY cd.week_end DESC
            LIMIT :limit OFFSET :offset
        )
        -- 2. Fetch full data only for those paginated weeks
        SELECT
            cd.week_end,
            dt.code AS dismantle_code,
            {", ".join(case_columns)}
        FROM cpe_dismantle cd

        JOIN weeks w ON w.week_end = cd.week_end

        JOIN dismantle_types dt ON dt.id = cd.dismantle_type_id

        LEFT JOIN cpe_types ct ON ct.id = cd.cpe_type_id

        WHERE {city_filter}
            AND cd.dismantle_type_id IN :d_list
            
        GROUP BY cd.week_end, dt.code
        ORDER BY cd.week_end DESC
    """

    # Because SQL already does:
    # GROUP BY week_end, dismantle_code
    # Each row represents:
    # one week + one damage type + all CPE columns
    result = db.session.execute(text(SQL_QUERY), params)

    # pivoted_data is now list
    pivoted_data = [row._asdict() for row in result.all()]

    # paginate is iterable SimplePagination object
    paginate = SimplePagination(
        page=page, per_page=per_page, total=total_count, items=pivoted_data
    )

    return paginate
