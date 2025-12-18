# commands.py (or cli.py)
from flask.cli import with_appcontext
import click  # Import current_app for the command context
from werkzeug.security import generate_password_hash
from models import db, Users
import datetime


@click.command("create-admin")  # Define the command name
@with_appcontext
def create_initial_admin(username="admin", plain_password="123"):
    """CLI command to create a default admin user."""


    password_hash = generate_password_hash(plain_password)

    admin = Users(
        username=username,
        password_hash=password_hash,
        city_id=None,
        role="admin",
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )

    existing_user = db.session.query(Users).filter_by(username=username).first()
    if existing_user:
        print(f"Admin user '{username}' already exists. Skipping insertion.")
        return

    try:
        db.session.add(admin)
        db.session.commit()
        print(f"Successfully created initial ADMIN user: {username}")
    except Exception as e:
        db.session.rollback()
        print(f"Error creating admin user: {e}")
