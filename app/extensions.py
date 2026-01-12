from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()

login_manager = LoginManager()

# This tells Flask-Login where to redirect unauthenticated users.
login_manager.login_view = "auth.login"
