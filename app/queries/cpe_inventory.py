from sqlalchemy import text
from app.extensions import db
from datetime import datetime
from app.utils.simplepagination import SimplePagination


def get_cpe_inventory_pivoted(schema_list: list, week_end: datetime.date):
    if not schema_list:
        # Return empty data lists immediately if no active CPE types are found
        return []

    case_columns = []
    sum_columns = []

    for model in schema_list:
        case_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN cpe_name = '{model["name"]}' THEN quantity END),
                0
            ) AS "{model["name"]}"
            """
        )
        sum_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN cpe_name = '{model["name"]}' THEN quantity END),
                0
            ) AS "{model["name"]}"
            """
        )

    SQL_QUERY = f"""
        WITH weekly_data AS (
            SELECT
                c.id   AS city_id,
                c.name AS city_name,
                c.include_in_total,
                ct.name AS cpe_name,
                ci.quantity AS quantity,
                ci.reported_at AS reported_at
            FROM cities c
            LEFT JOIN cpe_inventory ci
                ON c.id = ci.city_id
                --Use the latest available record whose week_end is ≤ current business Friday
                --Give me the latest week if we are in new week which doesnot have data yet
                AND ci.week_end =(
                SELECT MAX(ci2.week_end)
                FROM cpe_inventory ci2
                WHERE ci2.city_id=c.id
                AND ci2.week_end <= :week_end
                )
            LEFT JOIN cpe_types ct
                ON ct.id = ci.cpe_type_id
            WHERE c.is_active = true
        )
        SELECT
            city_id,
            city_name,
            {", ".join(case_columns)},
            MAX(reported_at) AS max_reported_at
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

    params = {"week_end": week_end}

    result = db.session.execute(text(SQL_QUERY), params)

    return [row._asdict() for row in result.all()]


def get_cpe_inventory_city_history(
    city_id: int, schema_list: list, page: int, per_page: int
):
    """
    Retrieves the historical records for a specific city_id, pivoted by CPE type.
    This query handles pagination internally based on the unique WEEK_END timestamp.
    """
    if not schema_list:
        # Return empty data lists immediately if no active CPE types are found
        return []

    # We need a separate query to get the total count for pagination
    count_query = text(
        """SELECT 
                COUNT(DISTINCT WEEK_END) 
            FROM CPE_INVENTORY 
            WHERE CITY_ID=:city_id
        """
    )

    total_count = db.session.execute(count_query, {"city_id": city_id}).scalar()

    # Calculate offset
    offset = (page - 1) * per_page

    case_columns = []

    for model in schema_list:
        case_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN ct.name = '{model["name"]}' THEN ci.quantity END),
                0
            ) AS "{model["name"]}"
            """
        )

    SQL_QUERY = f"""
        SELECT
            WEEK_END,
            {", ".join(case_columns)}
        FROM cpe_inventory ci
        LEFT JOIN cpe_types ct ON ct.id=ci.cpe_type_id
        WHERE ci.city_id = :city_id
        GROUP BY ci.WEEK_END
        ORDER BY ci.week_end DESC
        LIMIT :limit
        OFFSET :offset
    """

    params = {
        "city_id": city_id,
        "limit": per_page,
        "offset": offset,
    }

    result = db.session.execute(text(SQL_QUERY), params)

    # pivoted_data is now list
    pivoted_data = [row._asdict() for row in result.all()]

    # paginate is iterable SimplePagination object
    paginate = SimplePagination(
        page=page, per_page=per_page, total=total_count, items=pivoted_data
    )

    return paginate
