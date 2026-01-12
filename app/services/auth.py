from werkzeug.security import check_password_hash
from flask_login import (
    login_user,
    logout_user,
    current_user,
)
from app.models import (
    Users,
)


def login_to_app(form_data):
    username = form_data.get("username")
    password = form_data.get("password")

    user = Users.query.filter_by(username=username).first()

    if user and check_password_hash(user.password_hash, password):
        # Flask will store user session in browser
        login_user(user)  # from flask-login packet
        return True, f"Dobrodošli, {username}"

    return False, "Invalid credentials"


def logout_from_app():
    if current_user.is_authenticated:
        username_to_flash = current_user.username
        logout_user()
        return True, f"Doviđenja, {username_to_flash}"
    return False, "Niste prijavljeni"
