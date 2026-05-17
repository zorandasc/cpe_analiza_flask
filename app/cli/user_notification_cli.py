import os
from datetime import datetime, timezone
import click
from flask.cli import with_appcontext
from flask import current_app
from exchangelib import (
    DELEGATE,
    Account,
    Configuration,
    Credentials,
)
from app.extensions import db
from app.services.user_notify import (
    get_stale_users_from_cpe_broken,
    get_stale_users_from_cpe_dismantle,
    get_stale_users_from_cpe_inventory,
    group_users,
    send_email_to_user,
)
from app.utils.dates import get_current_week_bounds


@click.command("notify_stale_city")
@with_appcontext
def notify_stale_city():

    # 1. Chek is .env variabla True or False
    if not current_app.config.get("ENABLE_CPE_NOTIFICATIONS", True):
        current_app.logger.info("CPE notifications are disabled via config.")
        return

    # ---------------------------------------------
    # 2. Get users for stale cities across all cpe tables
    # --------------------------------------------
    # Monday is now your baseline for freshness
    freshness_threshold = get_current_week_bounds()["monday"]


    users_inventory = get_stale_users_from_cpe_inventory(freshness_threshold)
    users_dismantle_comp = get_stale_users_from_cpe_dismantle(freshness_threshold, "complete")
    users_dismantle_miss = get_stale_users_from_cpe_dismantle(freshness_threshold, "missing")
    users_broken = get_stale_users_from_cpe_broken(freshness_threshold)

    users_to_notify = group_users(
        users_inventory, users_dismantle_comp, users_dismantle_miss, users_broken
    )

    # ----------------------------------------
    # 3. Send email notification to thal users
    # --------------------------------------------
    today = datetime.now(timezone.utc).date()

    credentials = Credentials(r"IN\cpe.reporting", os.environ.get("MAIL_PASSWORD"))
    config = Configuration(server="webmail.mtel.ba", credentials=credentials)
    account = Account(
        primary_smtp_address="cpe.reporting@mtel.ba",
        config=config,
        autodiscover=False,
        access_type=DELEGATE,
    )

    for user_data in users_to_notify.values():
        user = user_data["user"]

        # no email
        if not user.email:
            continue

        # one email per day per user
        if user.last_notified_at and user.last_notified_at.date() == today:
            continue

        success, message = send_email_to_user(user_data, account)
        if success:
            user.last_notified_at = datetime.now(timezone.utc)
            db.session.commit()
            current_app.logger.info(message)
        else:
            current_app.logger.error(message)

    db.session.commit()
