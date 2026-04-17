from sqlalchemy import text
from app.extensions import db
from datetime import datetime
from app.utils.simplepagination import SimplePagination


def get_cpe_inventory_pivoted(schema_list: list, week_end: datetime.date):
    """
    Retrieves the  records for a all major city_id, pivoted by CPE type.
    This query handles pagination internally based on the unique WEEK_END timestamp.
    """
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
        WITH last_inventory AS (
            -- ✅ Efficiently get the table of the latest inventory record per city/cpe type
            -- from cpe_inventory table. (This is for Quantities).
            SELECT DISTINCT ON (city_id, cpe_type_id)
                city_id,
                cpe_type_id,
                quantity,
                updated_at
            FROM cpe_inventory
            WHERE week_end <= :week_end
            ORDER BY city_id, cpe_type_id, week_end DESC
        ),
        city_last_update AS (
            --✅ Get the table of the absolute latest 'Save' timestamp for every city
            -- from cpe_inventory, table(city_id, last_save)(This is for Last Save).
            SELECT city_id, MAX(updated_at) as last_save
            FROM cpe_inventory
            WHERE week_end <= :week_end
            GROUP BY city_id
        ),
        city_health AS (
            --✅ Determine the table with final 'updated_at' for the row
            -- this table(city_id, major_city_id,final_updated_at)
            -- (This is for updated_at Parent/Child relationship)
            SELECT 
                c.id AS city_id,
                COALESCE(c.parent_city_id, c.id) AS major_city_id,
                CASE 
                    --✅ If this is a parent city (has subcities)
                    WHEN EXISTS (SELECT 1 FROM cities WHERE parent_city_id = c.id) THEN (
                        --✅  take the MIN of its children's cities last saves
                        -- min of max updated_at of all cubbcities
                        SELECT MIN(clu.last_save)
                        FROM cities sub
                        --✅ Use LEFT JOIN so if a subcity has NO data, MIN becomes NULL
                        LEFT JOIN city_last_update clu ON clu.city_id = sub.id
                        WHERE sub.parent_city_id = c.id
                    )
                    --✅ If it's a standalone or subcity, just take its own last save
                    -- which is max updated_at
                    ELSE clu_self.last_save
                END AS final_updated_at
            FROM cities c

            LEFT JOIN city_last_update clu_self ON clu_self.city_id = c.id
        ),
        -- ✅ enriched last_inventory table with other atributes
        weekly_data AS (
            SELECT
                COALESCE(c.parent_city_id, c.id) AS major_city_id,
                c.id AS city_id,
                mc.name AS city_name,
                s.included_in_total_sum AS include_in_total,
                ct.name AS cpe_name,
                ri.quantity AS quantity
            FROM cities c

            JOIN city_visibility_settings s
                ON s.city_id = c.id
                AND s.dataset_key = 'cpe_inventory'

            LEFT JOIN cities mc 
                ON mc.id = COALESCE(c.parent_city_id, c.id)

            -- ✅ Use the pre-filtered CTE instead of a correlated subquery
            LEFT JOIN last_inventory ri
                ON c.id = ri.city_id

            LEFT JOIN cpe_types ct
                ON ct.id = ri.cpe_type_id

            WHERE s.is_visible = true
        ),
    
        subcity_counts AS (
            SELECT
                parent_city_id AS major_city_id,
                COUNT(*) AS subcity_count
            FROM cities c
            JOIN city_visibility_settings s
                ON s.city_id = c.id
                AND s.dataset_key = 'cpe_inventory'
            WHERE parent_city_id IS NOT NULL AND s.is_visible = true
            GROUP BY parent_city_id
        )
    
    SELECT
        wd.major_city_id AS city_id,
        wd.city_name,
        COALESCE(sc.subcity_count, 0) AS subcity_count,
        {", ".join(case_columns)},
        ch.final_updated_at AS max_updated_at
    FROM weekly_data wd
    
    LEFT JOIN subcity_counts sc
        ON sc.major_city_id = wd.major_city_id
    
    JOIN city_health ch ON ch.city_id = wd.major_city_id

    GROUP BY wd.major_city_id, wd.city_name, sc.subcity_count, ch.final_updated_at

    UNION ALL

    SELECT
        NULL,
        'UKUPNO',
        NULL,
        {", ".join(sum_columns)},
        NULL
    FROM weekly_data
    WHERE include_in_total = true
    ORDER BY city_id NULLS LAST;
    """

    result = db.session.execute(text(SQL_QUERY), params)

    return [row._asdict() for row in result.all()]


def get_cpe_inventory_city_history(
    city_id: int, schema_list: list, page: int, per_page: int, scope: str
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
            ci.city_id IN (
                SELECT id
                FROM cities
                WHERE id = :city_id
                OR parent_city_id = :city_id
            )
            """
    else:
        city_filter = "ci.city_id = :city_id"

    # We need a separate query to get the total count for pagination
    count_query = text(f"""
        SELECT COUNT(DISTINCT WEEK_END)
        FROM CPE_INVENTORY ci
        WHERE {city_filter}
    """)

    total_count = db.session.execute(count_query, {"city_id": city_id}).scalar()

    # Calculate offset
    offset = (page - 1) * per_page

    case_columns = []

    params = {
        "city_id": city_id,
        "limit": per_page,
        "offset": offset,
    }

    for i, model in enumerate(schema_list):
        place_holder = f"cpe_{i}"
        # build list of sql statement with parameterized values
        case_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN ct.id = :{place_holder} THEN ci.quantity END),
                0
            ) AS "{model["name"]}"
            """
        )
        # this will fill params object with: cpe_1= model[1], cpe_2=model[2],..
        params[place_holder] = model["id"]

    SQL_QUERY = f"""
        SELECT
            WEEK_END,
            {", ".join(case_columns)}
        FROM cpe_inventory ci
        LEFT JOIN cpe_types ct ON ct.id=ci.cpe_type_id
        WHERE {city_filter}
        GROUP BY ci.WEEK_END
        ORDER BY ci.week_end DESC
        LIMIT :limit
        OFFSET :offset
    """

    result = db.session.execute(text(SQL_QUERY), params)

    # pivoted_data is now list
    pivoted_data = [row._asdict() for row in result.all()]

    # paginate is iterable SimplePagination object
    paginate = SimplePagination(
        page=page, per_page=per_page, total=total_count, items=pivoted_data
    )

    return paginate


def get_cpe_inventory_subcities(
    schema_list: list, major_city_id: int, week_end: datetime.date
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
     WITH last_inventory AS (
        -- ✅ Efficiently get the latest inventory record per city/cpe type
        SELECT DISTINCT ON (city_id, cpe_type_id)
            city_id,
            cpe_type_id,
            quantity,
            updated_at
        FROM cpe_inventory
        WHERE week_end <= :week_end
        ORDER BY city_id, cpe_type_id, week_end DESC
        ),
        -- ✅ enriched last_inventory
        weekly_data AS (
            SELECT
                c.id   AS city_id,
                c.name AS city_name,
                s.included_in_total_sum AS include_in_total,
                ct.name AS cpe_name,
                ri.quantity AS quantity,
                ri.updated_at AS updated_at
            FROM cities c

            JOIN city_visibility_settings s
                ON s.city_id =c.id
                AND s.dataset_key = 'cpe_inventory'

            -- ✅ Use the pre-filtered CTE instead of a correlated subquery
            LEFT JOIN last_inventory ri
                ON c.id = ri.city_id

            LEFT JOIN cpe_types ct
                    ON ct.id = ri.cpe_type_id

            WHERE (c.id = :major_city_id OR c.parent_city_id = :major_city_id)
                AND s.is_visible = true
        )
        SELECT
            city_id,
            city_name,
            {", ".join(case_columns)},
            MAX(updated_at) AS max_updated_at
        FROM weekly_data
        GROUP BY city_id, city_name

        UNION ALL

        SELECT
            NULL,
            'UKUPNO',
            {", ".join(sum_columns)},
            NULL
        FROM weekly_data
        --EXCLUDE RASPLOZIVA OPREMA
        WHERE include_in_total = true

        ORDER BY city_id NULLS LAST;
    """

    result = db.session.execute(text(SQL_QUERY), params)

    return [row._asdict() for row in result.all()]
