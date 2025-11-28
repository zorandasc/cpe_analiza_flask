# commands.py (or cli.py)
from flask.cli import with_appcontext
import click
from models import db

@click.command("init-db")
@with_appcontext
def create_initial_db():
    """CLI command to initialize the database schema."""
    
    # 1. Start message
    click.echo("--- Starting database schema initialization (db.create_all()) ---")
    
    try:
        # Run the command to create tables (if they don't exist)
        db.create_all()
        
        # 2. Success message
        click.echo("--- Database schema initialization SUCCESSFUL. All tables are ensured. ---")
        
    except Exception as e:
        # 3. Error handling message
        click.echo(f"!!! Database schema initialization FAILED: {e}", err=True)
        # Re-raise the exception to stop the entrypoint.sh script
        raise

# Note: Using click.echo() is often preferred over standard print() in Flask CLI scripts
# because it handles output formatting and streams (like stderr for errors) correctly.