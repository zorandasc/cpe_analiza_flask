# Business logic + write operations
from sqlalchemy import text
from app.extensions import db
from app.models import Cities, CityTypeEnum
from app.utils.dates import get_current_week_friday, get_passed_saturday
from app.utils.permissions import can_access_city
from datetime import date
from app.utils.schemas import get_cpe_types_column_schema
from app.queries.cpe_dismantle import (
    get_cpe_dismantle_pivoted,
    get_cpe_dismantle_city_history,
)


def get_cpe_dismantle_view_data():
    # to display today date on title
    today = date.today()

    # SATURDAY of this week
    # to mark row (red) if updated_at less than
    saturday = get_passed_saturday()

    # date of friday in week
    current_week_end = get_current_week_friday()

    # list of all cpe_types object in db but only if is_active_dismantle
    schema_list = get_cpe_types_column_schema("is_active_dismantle")

    # 1. Build pivoted records from schema list but only for current week_end
    records = get_cpe_dismantle_pivoted(
        schema_list, current_week_end, city_type=CityTypeEnum.IJ.value
    )

    # ROWS IN records FROM RAW SQL, LOOK LIKE THIS:
    """"
    [{'city_id': 3, 'city_name': 'IJ Banja Luka', 'dismantle_type_id': 1, 
    'dismantle_code':COMP, 'IADS': 148, 'VIP4205_VIP4302_1113': 345,...,
    'complete_updated_at': datetime.datetime(2025, 12, 26, 0, 0),
    'missing_updated_at':datetime.datetime(2025, 12, 26, 0, 0)}...]
    """

    records_grouped = _group_records(records, schema_list)

    return {
        "today": today.strftime("%d-%m-%Y"),
        "saturday": saturday,
        "current_week_end": current_week_end.strftime("%d-%m-%Y"),
        "schema": schema_list,
        "dismantle": records_grouped,
    }


def update_cpe_dismantle(data):
    city_id = data["city_id"]
    city_name = data["city"]
    updates = data["updates"]

    if not city_id or not updates:
        return False, "Neispravan payload."

    if not can_access_city(city_id):
        return False, "Niste autorizovani."

    week_end = get_current_week_friday()

    # Temporal Snapshot with Partial Mutation
    ensure_snapshot(city_id, week_end)

    # 3: Apply updates
    for u in updates:
        if u["quantity"] is None:
            continue
        stmt = text("""
            INSERT INTO cpe_dismantle (
                  city_id, cpe_type_id, dismantle_type_id, week_end, quantity 
                ) 
            VALUES (:city_id, :cpe_type_id, :dismantle_type_id, :week_end, :quantity)
            ON CONFLICT (city_id, cpe_type_id, dismantle_type_id, week_end)
            DO UPDATE SET 
                quantity = EXCLUDED.quantity,
                updated_at = now()

        """)
        db.session.execute(
            stmt,
            {
                "city_id": city_id,
                "cpe_type_id": u["cpe_type_id"],
                "dismantle_type_id": u["dismantle_type_id"],
                "week_end": week_end,
                "quantity": u["quantity"],
            },
        )
    try:
        db.session.commit()
        return True, f"Novo stanje za skladište {city_name} uspješno sačuvano!"
    except Exception as e:
        db.session.rollback()
        print(f"Error during CpeDismantle batch insert: {e}")
        return False, "Došlo je do greške prilikom unosa u bazu."


def get_cpe_dismantle_history(id: int, page: int, per_page: int, category: str):
    # POSALJI ISTORIJSKU PAGINACIJU ZA TAJ GRAD
    city = Cities.query.get(id)

    if not city:
        return None, None, None, None, "Grad ne postoji."

    if not can_access_city(city.id):
        return None, None, None, None, "Niste autorizovani."

    if category not in ("complete", "damage"):
        return None, None, None, None, "No Category"

    # list of all cpe_types object in db but only if is_active_dismantle
    schema_list = get_cpe_types_column_schema("is_active_dismantle")

    # paginated_records is iterable SimplePagination object
    records = get_cpe_dismantle_city_history(
        city_id=city.id, schema_list=schema_list, page=page, per_page=per_page
    )

    records.items = _group_history_records(records.items, schema_list)

    return city, records, schema_list, category, None


def get_cpe_dismantle_excel_export(mode: str):  # mode: str,  # "complete" | "missing"
    current_week_end = get_current_week_friday()

    schema_list = get_cpe_types_column_schema("is_active_dismantle")

    records = get_cpe_dismantle_pivoted(
        schema_list, current_week_end, city_type=CityTypeEnum.IJ.value
    )

    grouped = _group_records(records, schema_list)

    # APPLY Excel adapter
    headers_main = ["Skladišta"]
    headers_sub = [""]

    rows = []

    # FOR COMPLETE HEADER, SUBHEADER:
    # If cpe["label"] is "Router"
    # headers_main.append("Router")
    # headers_main: ["Skladišta", "Router", "Azururano"]
    # headers_sub:  ["",          "kolicina",     ""]

    # FOR DAMAGE HEADER, SUBHEADER:
    # If cpe["label"] is "Router"
    # headers_main.extend(["Router", "Router", "Router"])
    # headers_main: ["Skladišta", "Router",     "Router",   "Router",   "Azururano"]
    # headers_sub:  ["",    "Bez daljinskog", "Bez adaptera", "Bez oba",    ""]

    # append would have accidentally put a whole list inside your list,
    # extend keeps the list "flat" so you can iterate through it easily

    if mode == "complete":
        for cpe in schema_list:
            headers_main.append(cpe["label"])
            headers_sub.append("Količina")
    else:
        for cpe in schema_list:
            headers_main.extend([cpe["label"]] * 3)
            headers_sub.extend(["Bez adaptera", "Bez daljinskog", "Bez oba"])

    headers_main.append("Ažurirano")

    headers_sub.append("")

    # FOR COMPLETE DATA:
    # row=["ij banja luka", 10, "update_at","ij prijedor", 10, "update_at",...]
    # FOR DEMAGE DATA:
    # row=["ij banja luka", 10, 20, 30 "update_at", "ij prijedor", 10,20,30 "update_at"...]
    for city in grouped:
        row = [city["city_name"]]

        for cpe in schema_list:
            if mode == "complete":
                row.append(city["cpe"][cpe["name"]]["damages"]["comp"]["quantity"])
            else:
                row.extend(
                    [
                        city["cpe"][cpe["name"]]["damages"]["na"]["quantity"],
                        city["cpe"][cpe["name"]]["damages"]["nd"]["quantity"],
                        city["cpe"][cpe["name"]]["damages"]["ndia"]["quantity"],
                    ]
                )
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
                "city_id": row["city_id"],
                "city_name": row["city_name"],
                "complete_updated_at": row["complete_updated_at"],
                "missing_updated_at": row["missing_updated_at"],
                "cpe": {
                    cpe["name"]: {
                        "cpe_type_id": cpe["id"],
                        "damages": {
                            "comp": {"quantity": 0, "dismantle_type_id": 1},
                            "nd": {"quantity": 0, "dismantle_type_id": 2},
                            "na": {"quantity": 0, "dismantle_type_id": 3},
                            "ndia": {"quantity": 0, "dismantle_type_id": 4},
                        },
                    }
                    for cpe in schema_list
                },
            }
        else:
            city = grouped[cid]

            # Never overwrite timestamps once initialized
            # Always take the MAX defensively in Python
            # Update timestamps using max() while looping, just like SQL does.
            if row["complete_updated_at"]:
                city["complete_updated_at"] = max(
                    filter(
                        None, [city["complete_updated_at"], row["complete_updated_at"]]
                    )
                )

            if row["missing_updated_at"]:
                city["missing_updated_at"] = max(
                    filter(
                        None, [city["missing_updated_at"], row["missing_updated_at"]]
                    )
                )

        # IF ADDING NEW CITY "dismantle_code WILL BE NULL
        # If dismantle_code is None, it means it's an empty city row from the LEFT JOIN
        if row.get("dismantle_code"):
            for cpe in schema_list:
                qty = row.get(cpe["name"], 0)

                grouped[cid]["cpe"][cpe["name"]]["damages"][
                    row["dismantle_code"].lower()
                ] = {
                    "quantity": qty,
                    "dismantle_type_id": row["dismantle_type_id"],
                }

    return list(grouped.values())


# Temporal Snapshot with Partial Mutation
# WHY ensure_snapshot()? BECAUSE WE HAVE PARTIAL UPDATE POSSIBILITY
# AND WE IN CPE_DISMANTLE ROUTE HOME DEMAND TO RETURN
# FOR ONE WEEK ALL DISMANTLE_TYPES
# IF WE MAKE PARTIAL UPDATED FOR NEW WEEK, WE WILL GET NULL FOR OTHER
# SO FOR NEW WEEK WE COPY OLD UNUPDATE DATA AND AFTER THAT UPSERT NEW UPDATED DATA
def ensure_snapshot(city_id, week_end):
    # 1. CHECK IF CITY_ID/WEEK_END COMBINATION ALREADY EXISTS
    # Detect first update of week
    exists = db.session.execute(
        text("""
      SELECT 1 FROM cpe_dismantle
      WHERE city_id = :city_id AND week_end = :week_end
      LIMIT 1
    """),
        {"city_id": city_id, "week_end": week_end},
    ).scalar()

    # 2. IF YES RETURN
    if exists:
        return

    # 3. IF NO COPY DATA FROM LAST WEEK_END TO THIS WEEK_END
    # clone previous week row: week_end < :week_end
    db.session.execute(
        text("""
      INSERT INTO cpe_dismantle (
        city_id, cpe_type_id, dismantle_type_id, week_end, quantity, updated_at
      )
      SELECT
        city_id, cpe_type_id, dismantle_type_id, :week_end, quantity, updated_at
      FROM cpe_dismantle
      WHERE city_id = :city_id
        AND week_end = (
          SELECT MAX(week_end)
          FROM cpe_dismantle
          WHERE city_id = :city_id
            AND week_end < :week_end
        )
    """),
        {"city_id": city_id, "week_end": week_end},
    )


def _group_history_records(records, schema_list):
    grouped = {}

    for row in records:
        week = row["week_end"]

        if week not in grouped:
            grouped[week] = {
                "week": row["week_end"],
                "cpe": {
                    cpe["name"]: {
                        "cpe_type_id": cpe["id"],
                        "damages": {
                            "comp": {"quantity": 0},
                            "nd": {"quantity": 0},
                            "na": {"quantity": 0},
                            "ndia": {"quantity": 0},
                        },
                    }
                    for cpe in schema_list
                },
            }

        # IF ADDING NEW CITY "dismantle_code WILL BE NULL
        # If dismantle_code is None, it means it's an empty city row from the LEFT JOIN
        if row.get("dismantle_code"):
            for cpe in schema_list:
                qty = row.get(cpe["name"], 0)

                damage_key = row["dismantle_code"].lower()

                grouped[week]["cpe"][cpe["name"]]["damages"][damage_key]["quantity"] = (
                    qty
                )

    return list(grouped.values())
