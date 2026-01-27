# commands.py (or cli.py)
from flask.cli import with_appcontext
import click
from app.models import ReportSetting
from app.extensions import db
import datetime


# report_settings should behave as singleton configuration table
# in another word table should have ONLY ONE ROW
@click.command("create-report")  # Define the command name
@with_appcontext
def create_initial_report():
    """Create default singleton report settings."""

    if ReportSetting.query.first():
        click.echo("Report settings already exist")
        return

    report = ReportSetting(
        enabled=True,
        send_day=4,  # Friday
        send_time=datetime.time(7, 0),  # informational only
    )

    try:
        db.session.add(report)
        db.session.commit()
        click.echo("Weekly report settings created")
    except Exception as e:
        db.session.rollback()
        click.echo(f"Error creating report settings: {e}")
