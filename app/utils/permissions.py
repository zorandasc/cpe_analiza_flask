from flask_login import current_user
from app.models import UserRole


# AUTHORIZATION ZA BILO KOJU AKCIJU: ONLY ADMIN
def admin_required():
    if current_user.is_authenticated and current_user.role == UserRole.ADMIN:
        return True
    return False


# AUTHORIZACIJA ZA CPECIFICNU AKCIJU: ADMIN OR USER AKO JE NJEGOV RESURS
# The helper function admin_and_user_required(city_id) handles access based
# on role ("admin") or resource ownership (current_user.city_id == city_id).
def can_access_city(city_id):
    if not current_user.is_authenticated:
        return False
    try:
        return (
            str(current_user.city_id) == str(city_id)
            or current_user.role == UserRole.ADMIN
        )
    except Exception:
        return False


# AUTHORIZATION ZA VIEW:  ADMIN OR VIEW
def view_required():
    if current_user.is_authenticated and (
        current_user.role == UserRole.VIEW or current_user.role == UserRole.ADMIN
    ):
        return True
    return False
