from sqlalchemy import text
from app.extensions import db
from datetime import datetime
from app.utils.simplepagination import SimplePagination


def get_cpe_broken_pivoted(schema_list: list, week_end: datetime.date, city_type: str):
    if not schema_list:
        # Return empty data lists immediately if no active CPE types are found
        return []

    case_columns = []
    sum_columns = []

    params = {"week_end": week_end, "city_type": city_type}

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
        WITH weekly_data AS (
            SELECT
                c.id   AS city_id,
                c.name AS city_name,
                c.include_in_total,
                ct.name AS cpe_name,
                ci.quantity AS quantity,
                ci.updated_at AS updated_at
            FROM cities c
            LEFT JOIN cpe_broken ci
                ON c.id = ci.city_id
                --Use the latest available record whose week_end is ≤ current business Friday
                --Give me the latest week if we are in new week which doesnot have data yet
                AND ci.week_end =(
                SELECT MAX(ci2.week_end)
                FROM cpe_broken ci2
                WHERE ci2.city_id=c.id
                AND ci2.week_end <= :week_end
                )
            LEFT JOIN cpe_types ct
                ON ct.id = ci.cpe_type_id
            WHERE C.TYPE = :city_type
                    AND c.is_active = true
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


def get_cpe_broken_city_history(
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
            FROM cpe_broken 
            WHERE CITY_ID=:city_id
        """
    )

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
        FROM cpe_broken ci
        LEFT JOIN cpe_types ct ON ct.id=ci.cpe_type_id
        WHERE ci.city_id = :city_id
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
