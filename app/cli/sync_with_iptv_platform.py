from collections import defaultdict
import click
from flask.cli import with_appcontext
import requests
from sqlalchemy import text
from app.extensions import db
from app.models import STBExternalMap
from app.services.user_activity_log import log_user_action
from app.utils.dates import get_current_week_friday


@click.command("sync-with-iptv")
@with_appcontext
def sync_stb_and_iptv():

    try:
        sync_stb_types_and_inventory()
    except Exception as e:
        db.session.rollback()
        print("STB sync failed:", e)

    try:
        sync_iptv_users()
    except Exception as e:
        db.session.rollback()
        print("IPTV users sync failed:", e)


def sync_stb_types_and_inventory():

    response = requests.get("http://10.152.0.17:8090/api/device-models")
    data = response.json()

    current_week_end = get_current_week_friday()

    # preload mappings
    mappings = {m.external_id: m for m in STBExternalMap.query.all()}

    updates_log = []

    aggregated = defaultdict(int)

    for item in data["data"]:
        ext_id = int(item["id"])
        quantity = int(item["total_count"])

        # FIND MAPPING OBJECT
        mapping = mappings.get(ext_id)

        if not mapping:
            continue

        # FROM MAPPING OBJECT FIND STB FROM STB_TYPES
        stb = mapping.stb_type

        # AGREGATE QUANTITTES FOR THAT STB_TYPE
        aggregated[mapping.stb_type_id] += quantity

    for stb_type_id, quantity in aggregated.items():
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
        updates_log.append(
            {
                "stb_type_id": stb_type_id,
                "stb_name": stb.name,
                "quantity": quantity,
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

    total_users = int(data["data"])

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
            "total_users": total_users,
            "week_end": current_week_end,
        },
    )

    log_user_action(
        action="update",
        table_name="IPTV Korisnici",
        details={
            "Sedmica": str(current_week_end),
            "Broj korisnika": total_users,
        },
        user_id=0,
    )

    db.session.commit()
