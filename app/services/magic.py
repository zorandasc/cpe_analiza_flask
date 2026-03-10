from itsdangerous import URLSafeTimedSerializer
from itsdangerous import BadSignature, SignatureExpired
from flask import current_app, url_for

from app.models import UserRole, Users


# 1. TOKEN GENERATOR TO EMBED IN LINK
def generate_login_token(user):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return serializer.dumps(user.id, salt="email-login")


# 2. GENERATE MAGIC LINK WITH TOKEN
def generate_link_for_view_user():

    # GET VIEW USER
    view_user = Users.query.filter_by(username="view", role=UserRole.VIEW).first()

    if not view_user:
        raise Exception("Korisnika sa imenom view i rolom view, mora da postoji na sistemu.")

    # EMBED USER IN TOKEN
    token = generate_login_token(view_user)

    base_url = current_app.config["APP_BASE_URL"]

    # GENERATE LINK WITH EMBEDED TOKEN TO ROUTE
    login_link = f"{base_url}/magic-login/{token}"

    return login_link


# USED IN ROUTE magic.magic_login  TO VERIFY TOKEN
def verify_login_token(token, max_age=43200):  # 12h
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        user_id = serializer.loads(token, salt="email-login", max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None

    return Users.query.get(user_id)
