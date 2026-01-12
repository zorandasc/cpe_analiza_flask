from sqlalchemy import text
from app.extensions import db


def get_stb_quantity_chart_data():
    rows = db.session.execute(
        text("""
    SELECT week_end, SUM(quantity) AS total
    FROM stb_inventory 
    GROUP BY week_end
        ORDER BY week_end                      

    """)
    ).fetchall()

    labels = [r.week_end.strftime("%d-%m-%Y") for r in rows]
    data = [r.total for r in rows]

    return {
        "labels": labels,
        "data": data,
    }
