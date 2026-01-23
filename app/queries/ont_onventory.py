from sqlalchemy import text
from app.extensions import db


def get_last_4_months():
    SQL = """ 
        SELECT DISTINCT month_end
        FROM ont_inventory
        ORDER BY month_end DESC
        LIMIT 4
    """
    rows = db.session.execute(text(SQL))

    return [row[0] for row in rows.all()]  # LIST OF DATES


def get_ont_inventory_pivoted(months: list):
    if not months:
        # Return empty data lists immediately if no active CPE types are found
        return []

    pivot_cols = []

    # This prevents SQL injection by using parameterized queries.
    params = {}

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
            {", ".join(pivot_cols)},
            max(i.updated_at) AS last_updated
        FROM cities c
        LEFT JOIN ont_inventory i
            ON c.id=i.city_id
        WHERE C.TYPE = 'IJ' and c.is_active = true
        GROUP BY c.id, c.name
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
        )
        SELECT * 
        FROM final_data
        ORDER BY
            CASE WHEN name = 'UKUPNO' THEN 1 ELSE 0 END,
            id; 
    """

    rows = db.session.execute(text(SQL), params)

    return [row._asdict() for row in rows.all()]
