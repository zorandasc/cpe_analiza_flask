import os


# KADA NAPRAVIMO python app.py UNUTAR VS CODA, ODNOSNO IZ VANA
# DOCKER MREZE, GADJAMO DOKERIZOVANI POSTGRES 5431
# MEDJUTIM KADA DOKERIZUJEMO FLASK APP MI SMO U INTERNOM DOCKER
# OKRUZENJU I ONDA TREBA DA GADJAMAO 5342, ODNOSNO
# DB_PORT: 5432 U DOCKER COMPOSE
class Config:
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = os.environ.get("DB_PORT", "5431")
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASS = os.environ.get("DB_PASSWORD", "mypassword")
    DB_NAME = os.environ.get("DB_NAME", "mydb")

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask-login uses sessions to store temporary, user-specific data
    # (like the logged-in user's ID). To ensure this data can't be tampered with
    # by clients, Flask requires a SECRET_KEY to cryptographically sign the
    # session cookie.
    SECRET_KEY = os.environ.get(
        "SECRET_KEY", "a_very_long_and_random_string_for_security"
    )
