from sqlalchemy import text
from app.extensions import db
from app.utils.simplepagination import SimplePagination


def get_last_4_months():
    SQL = """ 
        SELECT DISTINCT month_end
        FROM access_inventory
        ORDER BY month_end DESC
        LIMIT 4
    """
    rows = db.session.execute(text(SQL))

    return [row[0] for row in rows.all()]  # LIST OF DATES


def get_access_inventory_pivoted(months: list, access_type_id):
    if not months:
        # Return empty data lists immediately if no active CPE types are found
        return []

    pivot_cols = []

    params = {"access_type_id": access_type_id}

    # This prevents SQL injection by using parameterized queries.
    # idx is number: 0,1,2,3,
    # m is date object
    for idx, m in enumerate(months):
        place_holder = f"m{idx}"  # THIS IS JUST PLACEHOLDERS m0,m1,m2,m3
        pivot_cols.append(
            f'MAX(CASE WHEN i.month_end=:{place_holder} THEN i.quantity END) AS "{m}"'
        )
        params[place_holder] = m

    # params={'m0': datetime.date(2026, 1, 9), 'm1': datetime.date(2026, 1, 2),
    # 'm2': datetime.date(2025, 11, 28), 'm3': datetime.date(2025, 11, 21)}

    # monthly_data is pivoted data
    SQL = f"""
        WITH monthly_data AS(SELECT
            c.id,
            c.name,
            s.included_in_total_sum AS included_in_total_sum,
            {", ".join(pivot_cols)},
            max(i.updated_at) AS last_updated
        FROM cities c

        JOIN city_visibility_settings s
                ON s.city_id =c.id
                AND s.dataset_key = 'access_inventory'

        JOIN access_types at
            ON at.id=:access_type_id
            AND at.is_active=true

        LEFT JOIN access_inventory i
            ON c.id=i.city_id
            AND i.access_type_id = at.id

        WHERE s.is_visible = true
        GROUP BY c.id, c.name, s.included_in_total_sum
        ),
        final_data AS (
            SELECT
                id,
                name,
                {", ".join([f'"{m}"' for m in months])},
                last_updated
            FROM monthly_data

            UNION ALL

            SELECT
                NULL AS id,
                'UKUPNO' AS name,
                {", ".join([f'COALESCE(SUM("{m}"),0)' for m in months])},
                NULL AS last_updated
            FROM monthly_data
            WHERE included_in_total_sum = true
        )
        SELECT * 
        FROM final_data
        ORDER BY
            CASE WHEN name = 'UKUPNO' THEN 1 ELSE 0 END,
            id; 
    """

    rows = db.session.execute(text(SQL), params)

    return [row._asdict() for row in rows.all()]


def get_access_inventory_history(
    access_type_id: int, schema_list: list, page: int, per_page: int
):
    """
    Retrieves the historical records for a specific access_type_id pivoted by City.
    This query handles pagination internally based on the unique WEEK_END timestamp.
    """
    if not schema_list:
        # Return empty data lists immediately if no active CPE types are found
        return []

    # Calculate offset
    offset = (page - 1) * per_page

    params = {
        "access_type_id": access_type_id,
        "limit": per_page,
        "offset": offset,
    }

    case_columns = []

    for i, city in enumerate(schema_list):
        place_holder = f"city_{i}"
        case_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN c.id = :{place_holder} THEN ai.quantity END),
                0
            ) AS "{city.name}"
            """
        )
        # this will fill params object with: city_1= city[1], cpe_2=city[2],..
        params[place_holder] = city.id

    # We need a separate query to get the total count for pagination
    COUNT_QUERY = text(
        """SELECT 
                COUNT(DISTINCT MONTH_END) 
            FROM access_inventory 
            WHERE access_type_id = :access_type_id
        """
    )

    total_count = db.session.execute(COUNT_QUERY, params=params).scalar()

    # main query
    SQL_QUERY = f"""
        SELECT
            month_end,
            {", ".join(case_columns)}
        FROM access_inventory ai
        LEFT JOIN cities c ON c.id=ai.city_id
        WHERE ai.access_type_id = :access_type_id
        GROUP BY ai.month_end
        ORDER BY ai.month_end DESC
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
