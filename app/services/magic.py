from itsdangerous import URLSafeTimedSerializer
from itsdangerous import BadSignature, SignatureExpired
from flask import current_app, url_for

from app.models import UserRole, Users


# TOKEN GENERATOR
def generate_login_token(user):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return serializer.dumps(user.id, salt="email-login")


# VERIFY TOKEN
def verify_login_token(token, max_age=43200):  # 12h
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        user_id = serializer.loads(token, salt="email-login", max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None

    return Users.query.get(user_id)


# GENERATE MAGIC LINK
def generate_link_for_view_user():

    view_user = Users.query.filter_by(username="view", role=UserRole.VIEW).first()

    if not view_user:
        raise Exception("View user not configured properly.")

    token = generate_login_token(view_user)

    login_link = url_for("magic.magic_login", token=token, _external=True)

    return login_link
