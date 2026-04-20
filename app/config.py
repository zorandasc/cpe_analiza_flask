import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

def str_to_bool(value):
    return str(value).lower() in ("true", "1", "yes", "on")

# KADA NAPRAVIMO python app.py UNUTAR VS CODA, ODNOSNO IZ VANA
# DOCKER MREZE, GADJAMO DOKERIZOVANI POSTGRES 5431
# MEDJUTIM KADA DOKERIZUJEMO FLASK APP MI SMO U INTERNOM DOCKER
# OKRUZENJU I ONDA TREBA DA GADJAMAO 5342, ODNOSNO
# DB_PORT: 5432 U DOCKER COMPOSE
class Config:
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = os.environ.get("DB_PORT", "5431")
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASS = os.environ.get("DB_PASS")
    DB_NAME = os.environ.get("DB_NAME", "mydb")

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # "http://10.198.3.92:5000"
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://10.198.3.92:5000")

    REMOTE_STB_API = os.environ.get(
        "REMOTE_STB_API", "http://10.152.0.17:8090/api/device-models"
    )
    REMOTE_IPTV_USER_API = os.environ.get(
        "REMOTE_IPTV_USER_API", "http://10.152.0.17:8090/api/total-users"
    )

    # Flask-login uses sessions to store temporary, user-specific data
    # (like the logged-in user's ID). To ensure this data can't be tampered with
    # by clients, Flask requires a SECRET_KEY to cryptographically sign the
    # session cookie.
    SECRET_KEY = os.environ.get("SECRET_KEY")

    CRON_JOB_SECRET = os.environ.get("CRON_JOB_SECRET")

    # this will be respected only if session.permanent=True
    # which is deffined in auth service
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)

    # FOR USER EMAIL NOTIFICATION
    ENABLE_CPE_NOTIFICATIONS = str_to_bool(
        os.environ.get("ENABLE_CPE_NOTIFICATIONS", "true")
    )
