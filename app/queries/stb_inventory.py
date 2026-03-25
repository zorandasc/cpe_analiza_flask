from sqlalchemy import text
from app.extensions import db
from app.utils.simplepagination import SimplePagination


def get_last_4_weeks():
    SQL = """ 
        SELECT DISTINCT week_end
        FROM stb_inventory
        ORDER BY week_end DESC
        LIMIT 4
    """
    rows = db.session.execute(text(SQL))

    return [row[0] for row in rows.all()]  # LIST OF DATES


def get_stb_inventory_pivoted(weeks: list):
    if not weeks:
        # Return empty data lists immediately if no active CPE types are found
        return []

    pivot_cols = []

    # This prevents SQL injection by using parameterized queries.
    params = {}

    # idx is number: 0,1,2,3,
    # w is week date object
    for idx, w in enumerate(weeks):
        place_holder = f"w{idx}"  # THIS IS JUST PLACEHOLDERS w0,w1,w2,w3
        pivot_cols.append(
            f'MAX(CASE WHEN i.week_end=:{place_holder} THEN i.quantity END) AS "{w}"'
        )
        params[place_holder] = w

    # params={'w0': datetime.date(2026, 1, 9), 'w1': datetime.date(2026, 1, 2),
    # 'w2': datetime.date(2025, 11, 28), 'w3': datetime.date(2025, 11, 21)}

    # weekly_data is pivoted data
    SQL = f"""
        WITH weekly_data AS(SELECT
            t.id,
            t.label,
            {", ".join(pivot_cols)},
            max(i.updated_at) AS last_updated
        FROM stb_types t
        LEFT JOIN stb_inventory i
            ON t.id=i.stb_type_id
        WHERE t.is_active=TRUE
        GROUP BY t.id, t.label
        ),
        final_data AS (
            SELECT
                id,
                label,
                {", ".join([f'"{w}"' for w in weeks])},
                last_updated
            FROM weekly_data

            UNION ALL

            SELECT
                NULL AS id,
                'UKUPNO' AS label,
                {", ".join([f'COALESCE(SUM("{w}"),0)' for w in weeks])},
                NULL AS last_updated
            FROM weekly_data
        )
        SELECT * 
        FROM final_data
        ORDER BY
            CASE WHEN label = 'UKUPNO' THEN 1 ELSE 0 END,
            label; 
    """

    rows = db.session.execute(text(SQL), params)

    return [row._asdict() for row in rows.all()]


def get_iptv_users():
    SQL_QUERY_IPTV_USERS = """
            SELECT
               total_users,
               week_end,
               updated_at
            FROM
                IPTV_USERS
            ORDER BY
                WEEK_END DESC
            LIMIT
                4
    """

    iptv_users_rows = db.session.execute(text(SQL_QUERY_IPTV_USERS)).fetchall()

    iptv_users = [row._asdict() for row in iptv_users_rows]

    iptv_users.reverse()

    return iptv_users


def get_stb_types():
    SQL_QUERY = """
            SELECT
               id,
               name,
               label
            FROM stb_types
            WHERE is_active = true
            ORDER BY
                id
    """

    stb_types_rows = db.session.execute(text(SQL_QUERY)).fetchall()

    stb_types = [row._asdict() for row in stb_types_rows]

    return stb_types


def get_stb_inventory_history(schema_list: list, page: int, per_page: int):
    """
    Retrieves the historical records pivoted by STB type.
    This query handles pagination internally based on the unique WEEK_END timestamp.
    """
    if not schema_list:
        # Return empty data lists immediately if no active CPE types are found
        return []

    # We need a separate query to get the total count for pagination
    count_query = text(
        """SELECT 
                COUNT(DISTINCT WEEK_END) 
            FROM STB_INVENTORY 
        """
    )

    total_count = db.session.execute(count_query).scalar()

    # Calculate offset
    offset = (page - 1) * per_page

    case_columns = []

    for model in schema_list:
        case_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN st.name = '{model["name"]}' THEN si.quantity END),
                0
            ) AS "{model["name"]}"
            """
        )

    SQL_QUERY = f"""
        SELECT
            WEEK_END,
            {", ".join(case_columns)}
        FROM stb_inventory si
        LEFT JOIN stb_types st ON st.id=si.stb_type_id
        GROUP BY si.WEEK_END
        ORDER BY si.week_end DESC
        LIMIT :limit
        OFFSET :offset
    """

    params = {
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
