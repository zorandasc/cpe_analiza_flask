# Business logic + write operations
from datetime import date
from sqlalchemy import text
from app.extensions import db
from app.models import Cities
from app.services.user_activity_log import log_user_action
from app.utils.dates import get_current_week_friday, get_passed_saturday
from app.utils.permissions import can_access_city, can_edit_cpe_type
from app.utils.schemas import get_cpe_types_column_schema
from app.queries.cpe_inventory import (
    get_cpe_inventory_pivoted,
    get_cpe_inventory_city_history,
    get_cpe_inventory_subcities,
)


def get_cpe_records_view_data():
    # to display today date on title
    today = date.today()

    # SATURDAY BEFORE MONDAY OF THIS WEEK
    # to mark row (red) if updated_at less than saturday
    saturday = get_passed_saturday()

    # DATE OF FRIDAY IN THIS WEEK
    current_week_end = get_current_week_friday()

    # list of all cpe_types object in db THAT ARE ACTIVE
    schema_list = get_cpe_types_column_schema("visible_in_total", "order_in_total")

    # Build pivoted cpe_inventory records fOR schema list but only for current week
    # RETURN PER CITY, QUANITY FOR ALL CPE_TYPES AND FOR LAST WEEK
    # SQL → records (flat rows)
    records = get_cpe_inventory_pivoted(schema_list, current_week_end)

    # list of grouped dicts for sending to template
    records_grouped = _group_records(records, schema_list)

    # ordering of rows, total penultimate, Rasploziva Oprema last
    records_grouped = _reorder_cpe_records(records_grouped)

    return {
        "today": today.strftime("%d-%m-%Y"),
        "saturday": saturday,
        "current_week_end": current_week_end.strftime("%d-%m-%Y"),
        "schema": schema_list,
        "records": records_grouped,
    }


def get_cpe_records_subcities(city_id: int):
    # to display today date on title
    today = date.today()

    # SATURDAY BEFORE MONDAY OF THIS WEEK
    # to mark row (red) if updated_at less than saturday
    saturday = get_passed_saturday()

    # DATE OF FRIDAY IN THIS WEEK
    current_week_end = get_current_week_friday()

    # list of all cpe_types object in db THAT ARE ACTIVE
    schema_list = get_cpe_types_column_schema("visible_in_total", "order_in_total")

    # Build pivoted cpe_inventory records fOR schema list but only for current week
    # RETURN PER CITY, QUANITY FOR ALL CPE_TYPES AND FOR LAST WEEK
    # SQL → records (flat rows)
    records = get_cpe_inventory_subcities(schema_list, city_id, current_week_end)

    # list of grouped dicts for sending to template
    records_grouped = _group_records(records, schema_list)

    return {
        "today": today.strftime("%d-%m-%Y"),
        "saturday": saturday,
        "current_week_end": current_week_end.strftime("%d-%m-%Y"),
        "schema": schema_list,
        "records": records_grouped,
    }


def update_cpe_records(data):
    # 1. Extract and Convert Fields
    try:
        city_id = int(data.get("city_id"))
    except (TypeError, ValueError):
        return False, "Neispravan city id."

    if not can_access_city(city_id):
        return False, "Niste autorizovani."

    city_name = data.get("city")

    updates = data.get("updates", [])

    if not updates:
        return False, "Neispravan payload."

    current_week_end = get_current_week_friday()

    applied_updates = []

    # We insert a new record for FOR ONE CITY_ID AND EVERY CPE type
    # UPSERT: INSERT IF city_id, cpe_type_id, week_end DONT EXSIST
    # UPDATE QUANTITY IF EXSIST
    try:
        for u in updates:
            if "cpe_type_id" not in u or "quantity" not in u:
                continue

            cpe_type_id = int(u.get("cpe_type_id"))
            quantity = max(0, int(u.get("quantity", 0)))

            if not can_edit_cpe_type(cpe_type_id):
                continue  # or return False, "Niste autorizovani za ovaj CPE tip."

            applied_updates.append(u)

            stmt = text("""
                INSERT INTO cpe_inventory ( 
                        city_id,
                        cpe_type_id,
                        week_end,
                        quantity,
                        updated_at
                    )
                    VALUES (:city_id,
                            :cpe_type_id,
                            :week_end,
                            :quantity,
                            NOW()
                            )
                    ON CONFLICT (city_id, cpe_type_id, week_end)
                    DO UPDATE SET quantity = EXCLUDED.quantity, updated_at = NOW();
                    """)

            db.session.execute(
                stmt,
                {
                    "city_id": city_id,
                    "cpe_type_id": cpe_type_id,
                    "week_end": current_week_end,
                    "quantity": quantity,
                },
            )

        log_user_action(
            action="update",
            table_name="CPE Oprema",
            details={
                "Sedmica": str(current_week_end),
                "Skladiste": city_name,
                "Unosi": applied_updates,
            },
        )

        db.session.commit()
        return True, f"Novo stanje za skladište {city_name} uspješno sačuvano!"
    except Exception as e:
        db.session.rollback()
        print(f"Error during CpeInventory batch insert: {e}")
        return False, "Došlo je do greške prilikom unosa u bazu."


def get_cpe_records_history(city_id: int, page: int, per_page: int, scope: str):
    # POSALJI ISTORIJSKU PAGINACIJU ZA TAJ GRAD
    city = Cities.query.get(city_id)

    if not city:
        return None, None, None, "Grad ne postoji."

    if not can_access_city(city.id):
        return None, None, None, "Niste autorizovani."

    # list of all cpe_types object in db THAT ARE ACTIVE
    schema_list = get_cpe_types_column_schema("visible_in_total", "order_in_total")

    # paginated_records is iterable SimplePagination object
    records = get_cpe_inventory_city_history(
        city_id=city.id,
        schema_list=schema_list,
        page=page,
        per_page=per_page,
        scope=scope,
    )

    return city, records, schema_list, None


def get_cpe_records_excel_export():
    current_week_end = get_current_week_friday()

    schema_list = get_cpe_types_column_schema("visible_in_total", "order_in_total")

    records = get_cpe_inventory_pivoted(schema_list, current_week_end)

    records_grouped = _group_records(records, schema_list)

    # ordering of rows, total penultimate, Rasploziva Oprema last
    records_grouped = _reorder_cpe_records(records_grouped)

    # ---- HEADERS ----
    headers = ["Stanje"] + [s["label"] for s in schema_list] + ["Ažurirano"]

    # ---- ROWS EXCEL ADAPTER----
    rows = []
    for r in records_grouped:
        rows.append(
            {
                "city_id": r["city_id"],
                "city_name": r["city_name"],
                "values": (
                    [r["city_name"]]
                    + [r["cpe"][s["name"]].get("quantity", 0) for s in schema_list]
                    + [
                        r["max_updated_at"].strftime("%Y-%m-%d %H:%M")
                        if r["max_updated_at"]
                        else ""
                    ]
                ),
            }
        )

    return headers, rows, current_week_end


# -------------------------
# INTERNAL HELPERS
# -------------------------
# _group_records Treat it as canonical domain model:
# data modeling, reporting needs, future exports
def _group_records(records, schema_list):
    grouped = {}

    for row in records:
        # city_id is None for TOTAL (UKUPNO) row
        cid = row["city_id"]

        if cid not in grouped:
            grouped[cid] = {
                "city_id": row["city_id"],
                "city_name": row["city_name"],
                "subcity_count": row.get("subcity_count", 0)
                if cid is not None
                else None,
                "max_updated_at": row["max_updated_at"],
                "cpe": {
                    cpe["name"]: {
                        "cpe_type_id": cpe["id"],
                        "quantity": 0,
                    }
                    for cpe in schema_list
                },
            }
        for cpe in schema_list:
            qty = row.get(cpe["name"], 0)

            grouped[cid]["cpe"][cpe["name"]]["quantity"] = qty

    return list(grouped.values())


# SET TOTAL ROW PENULTIMATE (PREDZADNJI)
# SET CITY_ID 13 (RASPOLOZIVA OPREMA) LAST
def _reorder_cpe_records(records, excluded_city_id=13):
    total_row = None
    warehouse_row = None
    normal_rows = []

    for row in records:
        if row["city_id"] is None:
            # UKUPNO
            total_row = row
        elif row["city_id"] == excluded_city_id:
            warehouse_row = row
        else:
            normal_rows.append(row)

    ordered = normal_rows

    if total_row:
        ordered.append(total_row)

    if warehouse_row:
        ordered.append(warehouse_row)

    return ordered
