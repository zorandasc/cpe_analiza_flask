from sqlalchemy import text
from app.extensions import db
from datetime import datetime
from app.utils.simplepagination import SimplePagination


def get_cpe_dismantle_pivoted(schema_list: list, week_end: datetime.date):
    if not schema_list:
        # Return empty data lists immediately if no active CPE types are found
        return []

    case_columns = []
    sum_columns = []

    params = {"week_end": week_end}

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
                city_id,
                cpe_type_id,
                dismantle_type_id,
                quantity,
                updated_at
            FROM cpe_dismantle
            WHERE week_end <= :week_end
            ORDER BY city_id, cpe_type_id, dismantle_type_id, week_end DESC
        ),

        -- The Enrichment Center -CTE
        latest_data AS (
            SELECT
                c.id AS city_id,
                COALESCE(c.parent_city_id, c.id) AS major_city_id,
                mc.name AS city_name,
                s.included_in_total_sum AS include_in_total,
                rd.cpe_type_id,
                ct.name AS cpe_name,
                rd.dismantle_type_id,
                dt.code AS dismantle_code,
                rd.quantity,
                rd.updated_at AS last_updated_at
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

            WHERE s.is_visible = true
        ),

        -- ✅ THIS WEEK UPDATES (STATUS ONLY, independent!) -CTE
        -- give MAX(updated_at) but only for this current_week
        -- if no updated_at for current_week return null
        this_week_updates AS (
            SELECT
                city_id,
                dismantle_type_id,
                MAX(updated_at) AS updated_at
            FROM cpe_dismantle
            WHERE week_end = :week_end
            GROUP BY city_id, dismantle_type_id
        ),

        -- ✅ SUBCITY COUNT -CTE
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
            ld.major_city_id AS city_id,
            ld.city_name,
            COALESCE(sc.subcity_count, 0) AS subcity_count,
            ld.dismantle_type_id,
            ld.dismantle_code,
            {", ".join(case_columns)},
            CASE 
                -- numbers of subcities that are updated=total number of subcities
                WHEN COUNT(DISTINCT ld.city_id) FILTER (WHERE ld.dismantle_type_id = 1 AND tw.updated_at IS NOT NULL) 
                    = COUNT(DISTINCT ld.city_id)
                THEN MAX(tw.updated_at) FILTER (WHERE ld.dismantle_type_id = 1)
                ELSE NULL
            END AS complete_updated_at,
            CASE 
                WHEN COUNT(DISTINCT ld.city_id) FILTER (WHERE ld.dismantle_type_id IN (2,3,4) AND tw.updated_at IS NOT NULL) 
                    = COUNT(DISTINCT ld.city_id)
                THEN MAX(tw.updated_at) FILTER (WHERE ld.dismantle_type_id IN (2,3,4))
                ELSE NULL
            END AS missing_updated_at
        FROM latest_data ld

        --  left join with this_week_updates CTE
        LEFT JOIN this_week_updates tw 
            ON tw.city_id = ld.city_id AND tw.dismantle_type_id = ld.dismantle_type_id
        
        --  left join with subcity_counts CTE
        LEFT JOIN subcity_counts sc 
            ON sc.major_city_id = ld.major_city_id

        GROUP BY ld.major_city_id, ld.city_name, sc.subcity_count, ld.dismantle_type_id, ld.dismantle_code

        UNION ALL

        -- ✅ TOTAL ROW
        SELECT
            NULL AS city_id,
            'UKUPNO' AS city_name,
            NULL AS subcity_count,
            dismantle_type_id,
            dismantle_code,
            {", ".join(sum_columns)},
            NULL AS complete_updated_at,
            NULL AS missing_updated_at
        FROM latest_data
        WHERE include_in_total = true
        GROUP BY dismantle_type_id, dismantle_code
        ORDER BY city_id, dismantle_type_id NULLS LAST;
    """
    result = db.session.execute(text(SQL_QUERY), params)

    return [row._asdict() for row in result.all()]


def get_cpe_dismantle_subcities(
    schema_list: list, week_end: datetime.date, major_city_id: int
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

    params = {"major_city_id": major_city_id, "week_end": week_end}

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
        WITH latest_data AS (
            SELECT
                c.id AS city_id,
                c.name AS city_name,
                s.included_in_total_sum AS include_in_total,

                cd_last.cpe_type_id,
                ct.name AS cpe_name,

                cd_last.dismantle_type_id,
                dt.code AS dismantle_code,

                cd_last.quantity,
                cd_last.updated_at AS last_updated_at

            FROM cities c

            JOIN city_visibility_settings s
                ON s.city_id = c.id
                AND s.dataset_key = 'cpe_dismantle'

            -- ✅ LAST KNOWN VALUE
            LEFT JOIN cpe_dismantle cd_last
                ON cd_last.city_id = c.id
                AND cd_last.week_end = (
                    SELECT MAX(cd2.week_end)
                    FROM cpe_dismantle cd2
                    WHERE cd2.city_id = c.id
                    AND cd2.cpe_type_id = cd_last.cpe_type_id
                    AND cd2.dismantle_type_id = cd_last.dismantle_type_id
                    AND cd2.week_end <= :week_end
                )

            LEFT JOIN dismantle_types dt
                ON dt.id = cd_last.dismantle_type_id

            LEFT JOIN cpe_types ct
                ON ct.id = cd_last.cpe_type_id

            WHERE (c.id = :major_city_id OR c.parent_city_id = :major_city_id)
            AND s.is_visible = true
        ),

        -- ✅ THIS WEEK STATUS
        this_week_updates AS (
            SELECT
                city_id,
                dismantle_type_id,
                MAX(updated_at) AS updated_at
            FROM cpe_dismantle
            WHERE week_end = :week_end
            GROUP BY city_id, dismantle_type_id
        )

        SELECT
            ld.city_id,
            ld.city_name,

            ld.dismantle_type_id,
            ld.dismantle_code,

            {", ".join(case_columns)},

            -- ✅ COMPLETE
            MAX(tw.updated_at) FILTER (
                WHERE ld.dismantle_type_id = 1
            ) AS complete_updated_at,

            -- ✅ MISSING
            MAX(tw.updated_at) FILTER (
                WHERE ld.dismantle_type_id IN (2,3,4)
            ) AS missing_updated_at

        FROM latest_data ld

        LEFT JOIN this_week_updates tw
            ON tw.city_id = ld.city_id
            AND tw.dismantle_type_id = ld.dismantle_type_id

        GROUP BY
            ld.city_id,
            ld.city_name,
            ld.dismantle_type_id,
            ld.dismantle_code

        UNION ALL

        SELECT
            NULL AS city_id,
            'UKUPNO' AS city_name,

            dismantle_type_id,
            dismantle_code,

            {", ".join(sum_columns)},

            NULL,
            NULL

        FROM latest_data
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
