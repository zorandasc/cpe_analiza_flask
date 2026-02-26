from .auth import auth_bp
from .main import main_bp
from .cpe_inventory import cpe_inventory_bp
from .cpe_dismantle import cpe_dismantle_bp
from .cpe_broken import cpe_broken_bp
from .stb_inventory import stb_inventory_bp
from .ont_inventory import ont_inventory_bp
from .charts import chart_bp
from .admin import admin_bp
from .reports import report_bp


def register_routes(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(cpe_inventory_bp)
    app.register_blueprint(cpe_dismantle_bp)
    app.register_blueprint(cpe_broken_bp)
    app.register_blueprint(stb_inventory_bp)
    app.register_blueprint(ont_inventory_bp)
    app.register_blueprint(chart_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(report_bp)
