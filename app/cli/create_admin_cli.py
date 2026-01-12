# commands.py (or cli.py)
from flask.cli import with_appcontext
import click
from werkzeug.security import generate_password_hash
from app.models import Users, UserRole
from app.extensions import db
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
        role=UserRole.ADMIN,
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
    )

    existing_user = db.session.query(Users).filter_by(username=username).first()
    if existing_user:
        click.echo(f"Admin user '{username}' already exists. Skipping insertion.")
        return

    try:
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Successfully created initial ADMIN user: {username}")
    except Exception as e:
        db.session.rollback()
        click.echo(f"Error creating admin user: {e}")
