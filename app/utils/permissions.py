from flask_login import current_user
from app.models import UserRole


# ADMIN AUTHORIZATION ZA BILO KOJU AKCIJU
def admin_required():
    if current_user.is_authenticated and current_user.role == UserRole.ADMIN:
        return True
    return False


def view_required():
    if current_user.is_authenticated and current_user.role == UserRole.VIEW:
        return True
    return False


# AUTHORIZATION ZA VIEW:  ADMIN OR VIEW
def admin_view_required():
    if current_user.is_authenticated and (
        current_user.role == UserRole.VIEW or current_user.role == UserRole.ADMIN
    ):
        return True
    return False


# CITY - PERMISION
# AUTHORIZACIJA ZA CPECIFICNU AKCIJU: ADMIN OR USER AKO JE NJEGOV RESURS.
# Cities define REQUIRED scope (must be assigned)
def can_access_city(city_id):

    if not current_user.is_authenticated:
        return False

    # Admin can access everything
    if current_user.role == UserRole.ADMIN or current_user.role == UserRole.VIEW:
        return True

    # If user has no assigment for city, than can not access nothing
    if not current_user.cities:
        return False

    # Check if user has this city assigned
    allowed_ids = {c.id for c in current_user.cities}
    return city_id in allowed_ids


# CPE - PERMISION
# CPE types define OPTIONAL restrictions (empty = full access)
def can_edit_cpe_type(cpe_id):

    if not current_user.is_authenticated:
        return False

    # Admin can access everything
    if current_user.role == UserRole.ADMIN:
        return True

    if current_user.cpe_types:
        if not hasattr(current_user, "_allowed_cpe_ids"):
            #Cache it on user object:
            current_user._allowed_cpe_ids = {c.id for c in current_user.cpe_types}
        # Check if user has this cpe assigned
        return cpe_id in current_user._allowed_cpe_ids 

    # User can access all cpe types
    return True


# CITY-CPE PERMISION COMBINED
def can_edit_city_cpe(city_id, cpe_id):
    return can_access_city(city_id) and can_edit_cpe_type(cpe_id)


# AUTHORIZACIJA ZA IPTV PLATOFRMU
def iptv_view_required():
    if current_user.is_authenticated and (
        current_user.role == UserRole.USER_IPTV or current_user.role == UserRole.ADMIN
    ):
        return True
    return False


def ftth_view_required():
    if current_user.is_authenticated and (
        current_user.role == UserRole.USER_FTTH or current_user.role == UserRole.ADMIN
    ):
        return True
    return False
