from collections import defaultdict

from exchangelib import (
    HTMLBody,
    Mailbox,
    Message,
)
from flask import current_app, render_template
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Cities, CpeBroken, CpeInventory, DismantleCityWeekUpdate
from app.utils.dates import get_current_week_friday


def get_stale_users_from_cpe_inventory(saturday):
    # Find all cities that are stail or null from cpe_inventory
    cities = get_stale_cities_inventory(saturday)
    # Form users structure from that cities to send emails
    return map_cities_to_users(cities, "Stanje ukupno raspoložive CPE opreme")


label_map = {
    "complete": "Stanje demontirane kompletne CPE opreme",
    "missing": "Stanje demontirane nekompletne CPE opreme",
}


def get_stale_users_from_cpe_dismantle(saturday, group):
    # Find all cities that are stail or null from cpe_dismantle
    cities = get_stale_cities_dismantle(saturday, group)
    source = label_map[group]
    # Form users structure from that cities to send emails
    return map_cities_to_users(cities, source)


def get_stale_users_from_cpe_broken(saturday):
    # Find all cities that are stail or null from cpe_broken
    cities = get_stale_cities_broken(saturday)
    # Form users structure from that cities to send emails
    return map_cities_to_users(cities, "Stanje demontirane neispravne CPE opreme")


# return list of stale city_ids or city objects
# If a city has no record at all for current week → it must still be marked stale.
# This means: you cannot query only cpe_inventory you must start from Cities table
# and on that perform left join
def get_stale_cities_inventory(saturday):

    # DATE OF FRIDAY IN THIS WEEK
    current_week_end = get_current_week_friday()

    # Subquery: latest update per city for current week in cpe_inventory
    subq = (
        db.session.query(
            CpeInventory.city_id,
            func.max(CpeInventory.updated_at).label("last_update"),
        )
        .filter(CpeInventory.week_end == current_week_end)
        .group_by(CpeInventory.city_id)
        .subquery()
    )
    # Main query: LEFT JOIN subq with cities
    # return all cities with no rows or cities with stale updated_at
    # in cpe_inventory tsble
    query = (
        db.session.query(Cities)
        .outerjoin(subq, Cities.id == subq.c.city_id)
        .filter(
            or_(
                subq.c.last_update.is_(None),  # no row or never updated
                subq.c.last_update < saturday,
            )
        )
    )

    return query.all()


def get_stale_cities_dismantle(saturday, group):
    # ONLY query cpe_inventory
    # return list of city_ids or city objects
    # DATE OF FRIDAY IN THIS WEEK
    current_week_end = get_current_week_friday()

    # Subquery: latest update per city for current week in cpe_inventory
    subq = (
        db.session.query(
            DismantleCityWeekUpdate.city_id,
            DismantleCityWeekUpdate.updated_at.label("last_update"),
        )
        .filter(
            DismantleCityWeekUpdate.week_end == current_week_end,
            DismantleCityWeekUpdate.group_name == group,
        )
        .subquery()
    )
    # Main query: LEFT JOIN subq with cities (cities with no rows are still included)
    query = (
        db.session.query(Cities)
        .outerjoin(subq, Cities.id == subq.c.city_id)
        .filter(
            or_(
                subq.c.last_update.is_(None),  # no row or never updated
                subq.c.last_update < saturday,
            )
        )
    )

    return query.all()


def get_stale_cities_broken(saturday):

    # DATE OF FRIDAY IN THIS WEEK
    current_week_end = get_current_week_friday()

    # Subquery: latest update for city for current week in cpe_broken
    subq = (
        db.session.query(
            CpeBroken.city_id,
            func.max(CpeBroken.updated_at).label("last_update"),
        )
        .filter(CpeBroken.week_end == current_week_end)
        .group_by(CpeBroken.city_id)
        .subquery()
    )
    # Main query: LEFT JOIN subq with cities
    # return all cities with no rows or cities with stale updated_at
    # in cpe_inventory tsble
    query = (
        db.session.query(Cities)
        .outerjoin(subq, Cities.id == subq.c.city_id)
        .filter(
            or_(
                subq.c.last_update.is_(None),  # no row or never updated
                subq.c.last_update < saturday,
            )
        )
    )

    return query.all()



EXCLUDED_NOTIFICATION_ROLES = {"admin", "view", "user_iptv", "user_ftth"}


# JOIN ONE USER WHICH CAN HAVE MUTIPLE STALE CITIES FROM ONE CPE TABLE
def map_cities_to_users(cities, source):
    """
    join Users ↔ Cities (single query with eager loading)

    input:
    cities = [City1, City2, City3]
    source = "cpe_inventory"

    return:
    {
        user_id: {
            "user": user_obj,
            "cities": {
                "Banja Luka": ["cpe_inventory"],
                "Prijedor": ["cpe_inventory"]
            }
        }
    }
    """
    if not cities:
        return {}

    city_ids = [c.id for c in cities]

    # Load cities WITH users in one go (no 1+N)
    cities_with_users = (
        db.session.query(Cities)
        .options(selectinload(Cities.users))
        .filter(Cities.id.in_(city_ids))  # but filter by stail cities
        .all()
    )

    users_map = {}

    for city in cities_with_users:
        for user in city.users:
            # Skip users without email (optional safety)
            if not user.email:
                continue

            if user.role in EXCLUDED_NOTIFICATION_ROLES:
                continue

            if user.id not in users_map:
                users_map[user.id] = {"user": user, "cities": defaultdict(list)}

            users_map[user.id]["cities"][city.name].append(source)

    return users_map


# JOIN ONE USER STAIL CITIES FROM ALL CPE TABLES
def group_users(*user_maps):
    """
    Merge user stale cities from all cpe postgres tables per user:
    {
        1: {
            "user": user_obj,
            "cities": {
                "Banja Luka": ["cpe_inventory"],
                "Prijedor": ["cpe_inventory", "cpe_dismantle_complete"]
            }
        }
    }

    """
    result = {}

    # user_map is for one cpe tabel
    for user_map in user_maps:
        for user_id, data in user_map.items():
            if user_id not in result:
                result[user_id] = {"user": data["user"], "cities": defaultdict(list)}

            for city, sources_list in data["cities"].items():
                result[user_id]["cities"][city].extend(sources_list)

    return result


def send_email_to_user(user_data, account):
    """
    user_data is in this form:
    {
        1: {
            "user": user_obj,
            "cities": {
                "Banja Luka": ["Inventar CPE opreme"],
                "Prijedor": ["Inventar CPE opreme", "Kompletna demontaža"]
            }
        }
    }
    """

    user = user_data["user"]
    cities = user_data["cities"]

    subject = "[CPE Analiza] Obavještenje o neažuriranim podacima"

    app_url = current_app.config["APP_BASE_URL"]

    body_html = render_template(
        "notification/user_email.html", user=user, cities=cities, app_url=app_url
    )

    try:
        # 2. Create the Message
        message = Message(
            account=account,
            subject=subject,
            body=HTMLBody(body_html),
            to_recipients=[Mailbox(email_address=user.email)],
        )

        message.send_and_save()
        return True, f"Email sent to {user.email}"

    except Exception as e:
        return False, f"Email failed for {user.email}: {str(e)}"
