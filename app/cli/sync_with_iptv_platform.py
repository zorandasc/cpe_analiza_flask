import click
from flask.cli import with_appcontext
import requests
from sqlalchemy import text
from app.extensions import db
from app.models import StbTypes
from app.services.user_activity_log import log_user_action
from app.utils.dates import get_current_week_friday


@click.command("sync-with-iptv")
@with_appcontext
def sync_stb_and_iptv():

    try:
        sync_stb_types_and_inventory()
    except Exception as e:
        print("STB sync failed:", e)

    try:
        sync_iptv_users()
    except Exception as e:
        print("IPTV users sync failed:", e)


def sync_stb_types_and_inventory():
    response = requests.get("http://10.152.0.17:8090/api/device-models")
    data = response.json()

    # preload existing types
    types_map = {t.external_id: t for t in StbTypes.query.all()}

    # 1. THIS IS USE FOR REMOVAL OF STB IF ANY
    external_ids = set()

    # 1. SYNC STB TYPES
    for ext_type in data["types"]:
        ext_id = ext_type["id"]
        external_ids.add(ext_id)

        stb_type = types_map.get(ext_id)

        if not stb_type:
            stb_type = StbTypes(
                external_id=ext_id,
                name=ext_type["name"],
                label=ext_type.get("label"),
                is_active=True,
            )
            db.session.add(stb_type)
        else:
            stb_type.name = ext_type["name"]
            stb_type.label = ext_type.get("label")
            stb_type.is_active = True

    db.session.commit()  # ensure IDs exist

    # 2. DEACTIVATE REMOVED TYPES
    for stb in StbTypes.query.all():
        if stb.external_id not in external_ids:
            stb.is_active = False

    db.session.commit()

    # 3. AFTER StbTypes UPDATE UPSERT INVENTORY SNAPSHOT
    # If external system is source of truth → its time is also source of truth
    # week_end = parse_api_date(data["week_end"])
    current_week_end = get_current_week_friday()

    updates_log = []

    types_map = {t.external_id: t for t in StbTypes.query.all()}

    for item in data["inventory"]:
        stb_type = types_map.get(item["type_id"])

        if not stb_type:
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
                "stb_id": stb_type.id,
                "week_end": current_week_end,
                "quantity": item["quantity"],
            },
        )
        updates_log.append(
            {
                "stb_type_id": stb_type.id,
                "stb_label": stb_type.label,
                "quantity": item["quantity"],
            }
        )

    log_user_action(
        action="update",
        table_name="STB Oprema",
        details={
            "Sedmica": str(current_week_end),
            "Unosi": updates_log,
        },
        user_id=0,
    )
    db.session.commit()


def sync_iptv_users():
    response = requests.get("http://10.152.0.17:8090/api/total-users")
    data = response.json()

    current_week_end = get_current_week_friday()
    # If external system is source of truth → its time is also source of truth
    ## week_end = parse_api_date(data["week_end"])

    db.session.execute(
        text("""
        INSERT INTO iptv_users (total_users, week_end)
        VALUES (:total_users, :week_end)
        ON CONFLICT (week_end)
        DO UPDATE SET
            total_users = EXCLUDED.total_users,
            updated_at = NOW();
    """),
        {
            "total_users": data["total"],
            "week_end": current_week_end,
        },
    )

    log_user_action(
        action="update",
        table_name="IPTV Korisnici",
        details={
            "Sedmica": str(current_week_end),
            "Broj korisnika": data["total"],
        },
        user_id=0,
    )

    db.session.commit()
