# Business logic + write operations
from sqlalchemy import text
from app.extensions import db
from app.models import Cities, CityTypeEnum
from app.services.user_activity_log import log_user_action
from app.utils.dates import get_current_week_friday, get_passed_saturday
from app.utils.permissions import can_access_city, can_edit_cpe_type
from datetime import date
from app.utils.schemas import get_cpe_types_column_schema
from app.queries.cpe_dismantle import (
    get_cpe_dismantle_pivoted,
    get_cpe_dismantle_subcities,
    get_cpe_dismantle_city_history,
)


def get_cpe_dismantle_view_data():
    # to display today date on title
    today = date.today()

    # date of friday in week
    current_week_end = get_current_week_friday()

    # list of all cpe_types object in db but only if visible_in_dismantle
    schema_list = get_cpe_types_column_schema(
        "visible_in_dismantle", "order_in_dismantle"
    )

    # 1. Build pivoted records from schema list but only for current week_end
    complete_records = get_cpe_dismantle_pivoted(
        schema_list, current_week_end, group_name="complete"
    )

    missing_records = get_cpe_dismantle_pivoted(
        schema_list, current_week_end, group_name="missing"
    )

    return {
        "today": today.strftime("%d-%m-%Y"),
        "current_week_end": current_week_end.strftime("%d-%m-%Y"),
        "schema": schema_list,
        "complete_data": _group_records(complete_records, schema_list),
        "missing_data": _group_records(missing_records, schema_list),
    }


def get_cpe_dismantle_subcities_view(major_city_id: int, group_name: str):
    # to display today date on title
    today = date.today()

    # date of friday in week
    current_week_end = get_current_week_friday()

    # list of all cpe_types object in db but only if visible_in_dismantle
    schema_list = get_cpe_types_column_schema(
        "visible_in_dismantle", "order_in_dismantle"
    )

    # 1. Build pivoted records from schema list but only for current week_end
    records = get_cpe_dismantle_subcities(
        schema_list, current_week_end, major_city_id, group_name
    )

    records_grouped = _group_records(records, schema_list)

    return {
        "today": today.strftime("%d-%m-%Y"),
        "current_week_end": current_week_end.strftime("%d-%m-%Y"),
        "schema": schema_list,
        "dismantle": records_grouped,
    }


def update_cpe_dismantle(data):
    try:
        city_id = int(data.get("city_id"))
    except (TypeError, ValueError):
        return False, "Neispravan city id."

    if not can_access_city(city_id):
        return False, "Niste autorizovani."

    week_end = get_current_week_friday()

    city_name = data["city"]

    group_name = data["group_name"]

    updates = data["updates"]

    if not updates:
        return False, "Neispravan payload."

    applied_updates = []

    try:
        for u in updates:
            if (
                "cpe_type_id" not in u
                or "quantity" not in u
                or "dismantle_type_id" not in u
            ):
                continue

            cpe_type_id = int(u.get("cpe_type_id"))
            quantity = max(0, int(u.get("quantity", 0)))
            dismantle_type_id = int(u.get("dismantle_type_id"))

            if not can_edit_cpe_type(cpe_type_id):
                continue  # or return False, "Niste autorizovani za ovaj CPE tip."

            applied_updates.append(u)

            # 1. UPDATE THE MAIN TABLE (Quantities)
            stmt = text("""
                        INSERT INTO cpe_dismantle (
                            city_id, cpe_type_id, dismantle_type_id, week_end, quantity,updated_at,created_at 
                        ) 
                        VALUES (:city_id, :cpe_type_id, :dismantle_type_id, :week_end, :quantity, now(),now())
                        ON CONFLICT (city_id, cpe_type_id, dismantle_type_id, week_end)
                        DO UPDATE SET 
                            quantity = EXCLUDED.quantity,
                            updated_at = now()
                    """)

            db.session.execute(
                stmt,
                {
                    "city_id": city_id,
                    "cpe_type_id": cpe_type_id,
                    "dismantle_type_id": dismantle_type_id,
                    "week_end": week_end,
                    "quantity": quantity,
                },
            )
        # 2. UPDATE THE HELPER TABLE (Turns the dashboard row GREEN)
        helper_stmt = text("""
            INSERT INTO dismantle_city_week_update (city_id, week_end, group_name, updated_at)
            VALUES (:city_id, :week_end, :group_name, now())
            ON CONFLICT (city_id, week_end, group_name)
            DO UPDATE SET updated_at = now()
        """)

        db.session.execute(
            helper_stmt,
            {"city_id": city_id, "week_end": week_end, "group_name": group_name},
        )

        log_user_action(
            action="update",
            table_name="CPE Demontirana",
            details={
                "Sedmica": str(week_end),
                "Skladiste": city_name,
                "Unosi": applied_updates,
            },
        )

        db.session.commit()
        return True, f"Novo stanje za skladište {city_name} uspješno sačuvano!"
    except Exception as e:
        db.session.rollback()
        print(f"Error during CpeDismantle batch insert: {e}")
        return False, "Došlo je do greške prilikom unosa u bazu."


def get_cpe_dismantle_history(
    id: int, scope: str, category: str, page: int, per_page: int
):
    # POSALJI ISTORIJSKU PAGINACIJU ZA TAJ GRAD
    city = Cities.query.get(id)

    if not city:
        return None, None, None, None, "Grad ne postoji."

    if not can_access_city(city.id):
        return None, None, None, None, "Niste autorizovani."

    match category:
        case "complete":
            list_of_dismantles = [1]
        case "missing":
            list_of_dismantles = [2, 3, 4]
        case _:
            return None, None, None, None, "No Category"

    # list of all cpe_types object in db but only if visible_in_dismantle
    schema_list = get_cpe_types_column_schema(
        "visible_in_dismantle", "order_in_dismantle"
    )

    # paginated_records is iterable SimplePagination object
    records = get_cpe_dismantle_city_history(
        city_id=city.id,
        scope=scope,
        schema_list=schema_list,
        list_of_dismantles=list_of_dismantles,
        page=page,
        per_page=per_page,
    )

    records.items = _group_history_records(records.items, schema_list)

    return city, records, schema_list, category, None


def get_cpe_dismantle_excel_export(mode: str):  # mode: str,  # "complete" | "missing"
    current_week_end = get_current_week_friday()

    schema_list = get_cpe_types_column_schema(
        "visible_in_dismantle", "order_in_dismantle"
    )

    records = get_cpe_dismantle_pivoted(
        schema_list, current_week_end, city_type=CityTypeEnum.IJ.value
    )

    grouped = _group_records(records, schema_list)

    # APPLY Excel adapter
    headers_main = ["Skladišta"]
    headers_sub = [""]

    rows = []

    # -------------------------
    # HEADERS
    # -------------------------
    if mode == "complete":
        for cpe in schema_list:
            headers_main.append(cpe["label"])
            headers_sub.append("Količina")
    else:
        for cpe in schema_list:
            subcols = get_missing_subcolumns(cpe)

            if not subcols:
                continue

            headers_main.extend([cpe["label"]] * len(subcols))
            headers_sub.extend([label for _, label in subcols])

    headers_main.append("Ažurirano")
    headers_sub.append("")

    # -------------------------
    # ROWS
    # -------------------------
    for city in grouped:
        row = [city["city_name"]]

        for cpe in schema_list:
            if mode == "complete":
                row.append(city["cpe"][cpe["name"]]["missing"]["comp"]["quantity"])
            else:
                subcols = get_missing_subcolumns(cpe)
                for code, _ in subcols:
                    row.append(city["cpe"][cpe["name"]]["missing"][code]["quantity"])

        updated_at = (
            city["complete_updated_at"]
            if mode == "complete"
            else city["missing_updated_at"]
        )

        row.append(updated_at.strftime("%Y-%m-%d %H:%M") if updated_at else "")

        rows.append(row)

    return headers_main, headers_sub, rows, schema_list, current_week_end


# -------------------------
# INTERNAL HELPERS
# -------------------------
# _group_records Treat it as canonical domain model:
# data modeling, reporting needs, future exports
def _group_records(records, schema_list):
    grouped = {}

    for row in records:
        cid = row["city_id"]

        if cid not in grouped:
            grouped[cid] = {
                "city_id": cid,
                "city_name": row["city_name"],
                "subcity_count": row.get("subcity_count"),
                "updated_at": row["updated_at"],
                "is_stale": row["updated_at"] is None
                or row["updated_at"].date() < get_passed_saturday(),
                "data": {},  # key will be dismantle_code (e.g., 'COMP', 'ND')
            }

        # SQL gives us pivoted columns based on schema_list
        # We store the quantities mapped to the dismantle code
        d_code = row["dismantle_code"].lower() if row["dismantle_code"] else "unknown"

        grouped[cid]["data"][d_code] = {
            "dismantle_type_id": row["dismantle_type_id"],
            "quantities": {cpe["name"]: row.get(cpe["name"], 0) for cpe in schema_list},
        }

    return list(grouped.values())


# Because each row is of:
# one week + one missing type + all CPE columns
# we need to group → into one week object whick holds all missing + all CPE columns
# (comp row + nd row + na row + ndia row)
def _group_history_records(records, schema_list):
    """
    FOR EASY VIEW REPRESENTATION WE WANT OUR DATA TO LOOK LIKE THIS:

    {week: week_end1, cpe:[{cpe_type_id:1, "missing":{"comp":100,"nd":200, "na":300,"ndia":400}}, {cpe_type_id:2, "missing":{...}]},

    {week: week_end2, cpe:[{cpe_type_id:1, "missing":{"comp":100,"nd":200, "na":300,"ndia":400}}, {cpe_type_id:2, "missing":{...}]},

    """
    grouped = {}

    for row in records:
        # get week_end value form sql row
        week = row["week_end"]

        if week not in grouped:
            # forms group object by week (Each object is row in jinja table)
            grouped[week] = {
                # get week_end value form sql row
                "week": row["week_end"],
                "cpe": {
                    cpe["name"]: {
                        "cpe_type_id": cpe["id"],
                        "missing": {
                            "comp": {"quantity": 0},
                            "nd": {"quantity": 0},
                            "na": {"quantity": 0},
                            "ndia": {"quantity": 0},
                        },
                    }
                    for cpe in schema_list
                },
            }
        # get missing key form sql row
        missing_key = row.get("dismantle_code")

        if missing_key:
            missing_key = missing_key.lower()

            for cpe_name in grouped[week]["cpe"]:
                # id missing key in formed group object
                if missing_key in grouped[week]["cpe"][cpe_name]["missing"]:
                    # than take value from sql row
                    qty = row.get(cpe_name, 0)

                    # and put it inside group object for that week
                    grouped[week]["cpe"][cpe_name]["missing"][missing_key][
                        "quantity"
                    ] = qty

    return list(grouped.values())


# FOR BUILDING DINAMIC SUBHEADERS IN EXCEL
def get_missing_subcolumns(cpe):
    """
    FOR BUILDING DINAMIC SUBHEADERS IN EXCEL

    Returns dismantle subcolumns based on CPE capabilities.
    """
    sub = []

    if cpe["has_adapter"]:
        sub.append(("na", "Bez adaptera"))

    if cpe["has_remote"]:
        sub.append(("nd", "Bez daljinskog"))

    if cpe["has_adapter"] and cpe["has_remote"]:
        sub.append(("ndia", "Bez oba"))

    return sub
