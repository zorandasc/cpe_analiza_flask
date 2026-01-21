# Business logic + write operations
from sqlalchemy import text
from app.extensions import db
from app.utils.dates import get_current_month_end
from app.queries.ont_onventory import (
    get_last_4_months,
    get_ont_inventory_pivoted,
)


TOTAL_KEY = "__TOTAL__"


def get_ont_records_view_data():
    # calculate current week week_end date
    current_month_end = get_current_month_end()

    # month is used in SQL + and for structure of html table
    # covert datetime.date to date string
    # label → presentation used only in the table header
    # key → internal identifier (used in SQL + structure of html table)
    # w.isoformat()='YYYY-MM-DD'
    months = [
        {"key": m.isoformat(), "label": m.strftime("%d-%m-%Y")}
        for m in sorted(get_last_4_months())
    ]

    month_keys = [m["key"] for m in months]

    # get the pivoted data from db
    records = get_ont_inventory_pivoted(month_keys)

    records_grouped = _group_records(records, month_keys)

    return {
        "current_month_end": current_month_end.strftime("%d-%m-%Y"),
        "months": months,
        "records": records_grouped,
    }


def update_recent_ont_inventory(form_data):
    current_month_end = get_current_month_end()

    try:
        for key, value in form_data.items():
            if key == "__TOTAL__":
                continue
            try:
                city_id = int(key)
                quantity = int(value or 0)

            except ValueError:
                # Skip this record if ID or Quantity is invalid
                continue

            # because of UNIQUE (city_id, week_end) constraints
            # added when defining table OntInventory in postgres
            # business logic is: “For this month, insert if missing, update if exists”
            # That is exactly what PostgreSQL ON CONFLICT DO UPDATE is for.
            # ORM add_all() cannot do UPSERT cleanly
            db.session.execute(
                text("""
                    INSERT INTO ont_inventory (city_id, month_end, quantity)
                    VALUES (:city_id, :month_end, :quantity)
                    ON CONFLICT (city_id, month_end)
                    DO UPDATE SET quantity = EXCLUDED.quantity, updated_at = NOW();
                """),
                {
                    "city_id": city_id,
                    "month_end": current_month_end,
                    "quantity": quantity,
                },
            )

        # PostgreSQL loves batching UPSERTs in a single transaction.
        # UPSERT = “UPDATE or INSERT”.
        # Only on commit() does SQLAlchemy:
        # Send all pending SQL statements to the database
        # Wrap them in a transaction
        # `Make them permanent in the DB
        db.session.commit()
        return True, f"Novo stanje za {current_month_end} uspješno sačuvano!"

    except Exception as e:
        db.session.rollback()
        print(e)
        return False, "Greška prilikom čuvanja podataka."


def get_ont_records_excel_export():
    current_month_end = get_current_month_end()

    # month is used in SQL + and for structure of html table
    # covert datetime.date to date string
    # label → presentation used only in the table header
    # key → internal identifier (used in SQL + structure of html table)
    # w.isoformat()='YYYY-MM-DD'
    months = [
        {"key": m.isoformat(), "label": m.strftime("%d-%m-%Y")}
        for m in sorted(get_last_4_months())
    ]

    month_keys = [m["key"] for m in months]

    # get the pivoted data from db
    records = get_ont_inventory_pivoted(month_keys)

    records_grouped = _group_records(records, month_keys)

    # ---- HEADERS ----
    # ----STB HEADERS ----
    headers = ["Skladišta"] + month_keys

    rows = []
    for ont in records_grouped:
        row = [ont["name"]] + [ont["dates"][m]["quantity"] for m in month_keys]
        rows.append(row)

    return headers, rows, current_month_end


# -------------------------
# INTERNAL HELPERS
# -------------------------
def _group_records(records, month_keys):
    grouped = {}

    for row in records:
        cityid = row["id"] or TOTAL_KEY

        if cityid not in grouped:
            grouped[cityid] = {
                "id": cityid,
                "name": row["name"],
                "last_updated": row["last_updated"],
                "is_total": cityid == TOTAL_KEY,
                "dates": {month: {"quantity": 0} for month in month_keys},
            }

        for month in month_keys:
            grouped[cityid]["dates"][month]["quantity"] = row.get(month, 0)

    return list(grouped.values())
