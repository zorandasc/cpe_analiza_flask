from flask_login import current_user
from app.models import UserRole


#ADMIN AUTHORIZATION ZA BILO KOJU AKCIJU
def admin_required():
    if current_user.is_authenticated and current_user.role == UserRole.ADMIN:
        return True
    return False


# AUTHORIZACIJA ZA CPECIFICNU AKCIJU: ADMIN OR USER AKO JE NJEGOV RESURS.
def can_access_city(city_id):

    if not current_user.is_authenticated:
        return False

    # Admin can access everything
    if current_user.role == UserRole.ADMIN:
        return True

    # Check if user has this city assigned
    return any(c.id == city_id for c in current_user.cities)


# AUTHORIZATION ZA VIEW:  ADMIN OR VIEW
def view_required():
    if current_user.is_authenticated and (
        current_user.role == UserRole.VIEW or current_user.role == UserRole.ADMIN
    ):
        return True
    return False

#AUTHORIZACIJA ZA IPTV PLATOFRMU
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