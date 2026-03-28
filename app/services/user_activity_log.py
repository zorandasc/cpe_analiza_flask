from flask_login import current_user
from app.extensions import db
from app.models import UserActivity


def log_user_action(
    action: str,
    table_name: str = None,
    details=None,
    user_id: int = None,
):
    if details is None:
        details = {}

    # fallback to current_user if user_id not provided
    if user_id is None:
        if not current_user.is_authenticated:
            return
        user_id = current_user.id

    activity = UserActivity(
        user_id=user_id,
        action=action,
        table_name=table_name,
        details=details,
    )

    db.session.add(activity)