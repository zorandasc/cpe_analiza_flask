from flask import Flask
from flask_wtf.csrf import CSRFProtect
from app.config import Config
from app.extensions import db, login_manager
from app.models import Users
from app.routes import register_routes
from app.cli.create_admin_cli import create_initial_admin
from app.cli.create_db_tables_cli import create_initial_db
from app.cli.create_report_settings_cli import create_initial_report
from app.cli.sync_with_iptv_platform import sync_stb_and_iptv
from app.cli.user_notification_cli import notify_stale_city
from app.utils.permissions import (
    can_access_city,
    can_edit_cpe_type,
    admin_required,
    iptv_view_required,
    ftth_view_required,
    view_required,
)


def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        # static_folder="../static",
    )
    app.config.from_object(Config)

    # Flask automatically checks CSRF token
    # Every form that sends POST must include:
    # Before routes are used
    # all POST, PUT, PATCH, DELETE requests are protected
    # If token is missing or invalid → Flask returns 400 Bad Request.
    csrf = CSRFProtect(app)

    # Initialize SQLAlchemy with the app
    db.init_app(app)

    # Initialize Flask-Login
    login_manager.init_app(app)

    # While you defined the User model, you haven't yet registered the required user_loader
    # callback function with Flask-Login in your app.py. This function is absolutely mandatory
    # for Flask-Login to work.
    # The user_loader callback is a function that takes a user ID (as a string)
    # and returns the corresponding user object from your database,
    # or None if the ID is invalid.
    @login_manager.user_loader
    def load_user(user_id):
        return Users.query.get(int(user_id))

    # Register the command function with the Flask CLI
    # With this you can run mannualy in bash: flask command
    # or run it in script (entrypoint.sh)
    app.cli.add_command(create_initial_db)
    app.cli.add_command(create_initial_admin)
    app.cli.add_command(create_initial_report)
    app.cli.add_command(sync_stb_and_iptv)
    app.cli.add_command(notify_stale_city)

    # Register routes
    register_routes(app)

    # enable of insertions of function to jinja template
    @app.context_processor
    def inject_permissions():
        return dict(
            admin_required=admin_required,
            view_required=view_required,
            iptv_required=iptv_view_required,
            ftth_required=ftth_view_required,
            can_access_city=can_access_city,
            can_edit_cpe=can_edit_cpe_type,
        )

    return app
