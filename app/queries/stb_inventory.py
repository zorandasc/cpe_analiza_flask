from sqlalchemy import text
from app.extensions import db

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
               *
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
