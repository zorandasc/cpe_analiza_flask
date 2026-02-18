# Business logic + write operations
from sqlalchemy import text
from app.extensions import db
from app.utils.dates import get_current_week_friday
from app.utils.permissions import iptv_view_required
from app.queries.stb_inventory import (
    get_last_4_weeks,
    get_stb_inventory_pivoted,
    get_iptv_users,
    get_stb_inventory_history,
    get_stb_types,
)

TOTAL_KEY = "__TOTAL__"


def get_stb_iptv_records_view_data():
    # calculate current week week_end date
    current_week_end = get_current_week_friday()

    # covert datetime.date to date string
    # label → presentation (used only in the template
    # w.isoformat()='YYYY-MM-DD'
    weeks = [
        {"key": w.isoformat(), "label": w.strftime("%d-%m-%Y")}
        for w in sorted(get_last_4_weeks())
    ]

    # key → internal identifier (used in SQL + dict keys)
    week_keys = [w["key"] for w in weeks]

    # get the pivoted data from db
    records = get_stb_inventory_pivoted(week_keys)

    # records are:
    # [{'id': 1, 'label': 'STB A', '2025-01-05': 12, ...},
    # {'id': 2, 'label': 'STB B', '2025-01-05': 9, ...},
    # {'id': None, 'label': 'UKUPNO', '2025-01-05': 21, ...}]

    records_grouped = _group_records(records, week_keys)

    iptv_users = get_iptv_users()

    return {
        "current_week_end": current_week_end.strftime("%d-%m-%Y"),
        "weeks": weeks,
        "records": records_grouped,
        "iptv_users": iptv_users,
    }


def update_recent_stb_inventory(form_data):
    if not iptv_view_required():
        return False, "Niste autorizovani."
     
    current_week_end = get_current_week_friday()

    try:
        for key, value in form_data.items():
            if key == TOTAL_KEY:
                continue

            try:
                stb_type_id = int(key)
                quantity = int(value or 0)
            except ValueError:
                continue

            db.session.execute(
                text("""
                    INSERT INTO stb_inventory (stb_type_id, week_end, quantity)
                    VALUES (:stb_id, :week_end, :quantity)
                    ON CONFLICT (stb_type_id, week_end)
                    DO UPDATE SET
                        quantity = EXCLUDED.quantity,
                        updated_at = NOW();
                """),
                {
                    "stb_id": stb_type_id,
                    "week_end": current_week_end,
                    "quantity": quantity,
                },
            )

        db.session.commit()
        return True, f"Novo stanje za {current_week_end} uspješno sačuvano!"

    except Exception as e:
        db.session.rollback()
        print(e)
        return False, "Greška prilikom čuvanja podataka."


def update_iptv_users_count(form_data):
    current_week_end = get_current_week_friday()

    qty = form_data.get("qty")
    if not qty or not qty.isdigit():
        return False, "Molimo unesite ispravan broj.", "warning"

    try:
        db.session.execute(
            text("""
                    INSERT INTO iptv_users ( week_end, total_users)
                    VALUES ( :week_end, :total_users)
                    ON CONFLICT ( week_end)
                    DO UPDATE SET total_users = EXCLUDED.total_users, updated_at = NOW();
                    """),
            {
                "week_end": current_week_end,
                "total_users": qty,
            },
        )
        db.session.commit()
        return (
            True,
            f"Novo stanje za {current_week_end} uspješno sačuvano!",
        )

    except Exception as e:
        db.session.rollback()
        print(e)
        return False, "Greška prilikom čuvanja podataka.", "danger"


def get_stb_records_excel_export():
    # calculate current week week_end date
    current_week_end = get_current_week_friday()

    weeks = [
        {"key": w.isoformat(), "label": w.strftime("%d-%m-%Y")}
        for w in sorted(get_last_4_weeks())
    ]

    week_keys = [w["key"] for w in weeks]

    # get the pivoted data from db
    records = get_stb_inventory_pivoted(week_keys)

    records_grouped = _group_records(records, week_keys)

    iptv_users = get_iptv_users()

    # ----STB HEADERS ----
    headers_stb = ["STB Uređaji"] + week_keys

    # ----STB ROWS ----
    rows_stb = []
    for stb in records_grouped:
        row = [stb["label"]] + [stb["dates"][w]["quantity"] for w in week_keys]
        rows_stb.append(row)

    # header row
    headers_iptv = [""]

    # data row
    row_iptv = ["Ukupan broj IPTV korisnika"]

    for r in iptv_users:
        headers_iptv.append(r["week_end"].strftime("%d-%m-%Y"))
        row_iptv.append(r["total_users"])

    rows_iptv = [row_iptv]

    return headers_stb, rows_stb, headers_iptv, rows_iptv, current_week_end


def get_stb_records_history(page: int, per_page: int):

    # list of all cpe_types object in db THAT ARE ACTIVE
    schema_list = get_stb_types()

    for s in schema_list:
        print(s, "/n")

    # paginated_records is iterable SimplePagination object
    records = get_stb_inventory_history(
        schema_list=schema_list, page=page, per_page=per_page
    )

    return records, schema_list, None


# -------------------------
# INTERNAL HELPERS
# -------------------------
def _group_records(records, week_keys):
    grouped = {}

    for row in records:
        stbid = row["id"] or TOTAL_KEY

        if stbid not in grouped:
            grouped[stbid] = {
                "id": stbid,
                "label": row["label"],
                "last_updated": row["last_updated"],
                "is_total": stbid == TOTAL_KEY,
                "dates": {week: {"quantity": 0} for week in week_keys},
            }

        for week in week_keys:
            grouped[stbid]["dates"][week]["quantity"] = row.get(week, 0)

    return list(grouped.values())
