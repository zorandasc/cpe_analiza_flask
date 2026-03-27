from flask import session
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import (
    login_user,
    logout_user,
    current_user,
)
from app.extensions import db
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

        # Flask only respects expiration if the session is permanent.
        session.permanent = True

        return True, f"Dobrodošli, {username}"

    return False, "Invalid credentials"


def logout_from_app():
    if current_user.is_authenticated:
        username_to_flash = current_user.username
        logout_user()
        return True, f"Doviđenja, {username_to_flash}"
    return False, "Niste prijavljeni"


def change_my_password(current_password, new_password, confirm_password):
    # 1. Check current password
    if not check_password_hash(current_user.password_hash, current_password):
        return False, "Trenutna lozinka je netačna"

    # 2. Check new passwords match
    if new_password != confirm_password:
        return False, "Lozinke se ne poklapaju."

    # 3. Optional: enforce rules
    if len(new_password) < 6:
        return False, "Lozinka mora imati najmanje 6 karaktera."

    # 4. Save new password
    current_user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    return True, "Password updated successfully"
