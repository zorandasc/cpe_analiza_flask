from flask import Blueprint, render_template, request
from flask_login import login_required
from app.utils.schemas import get_cpe_types_column_schema
from app.models import CityTypeEnum, CpeTypeEnum
from app.services.charts import (
    get_cpe_inventory_chart_data,
    get_cpe_dismantle_chart_data,
    get_stb_inventory_chart_data,
    get_ont_inventory_chart_data,
    get_iptv_inventory_chart_data,
    get_distinct_joined_values,
)


chart_bp = Blueprint(
    "charts",
    __name__,
    url_prefix="/charts",
)


@chart_bp.route("/")
@login_required
def chart_home():
    return render_template("chart_home.html")


###########################################################
# ---------------ROUTES FOR GRAPHICAL-------------------------
############################################################
# GET REQUEST + query parameter FOR FILTERS
@chart_bp.route("/stb-charts", methods=["GET"])
@login_required
def stb_inventory_charts():
    # But still → submit GET params, GET + query parameter
    selected_id = request.args.get("id", type=int)

    selected_weeks = request.args.get("weeks", type=int)

    # ---------------------------------------
    # GET CHART DATA
    # ---------------------------------------
    chart_data = get_stb_inventory_chart_data(
        stb_type_id=selected_id, weeks=selected_weeks
    )

    # ---------------------------------------
    # FOR LISTING IN HTML SELECT ELEMENTS
    # ---------------------------------------
    stbs = get_distinct_joined_values(
        base_key="stb", join_key="stb_type", base_fk="stb_type_id"
    )

    # -----------------------------------
    # FOR BUILDING DYNAMIC TITLE IN CHART.JS
    # ---------------------------------------
    selected_stb_name = None
    if selected_id:
        selected_stb_name = next((c.label for c in stbs if c.id == selected_id), None)

    return render_template(
        "charts/stb_dashboard.html",
        chart_data=chart_data,
        stbs=stbs,
        selected_id=selected_id,
        selected_stb_name=selected_stb_name,
        selected_weeks=selected_weeks,
    )


# GET REQUEST + query parameter FOR FILTERS
@chart_bp.route("/iptv-users-charts", methods=["GET"])
@login_required
def iptv_inventory_charts():
    # But still → submit GET params, GET + query parameter

    selected_weeks = request.args.get("weeks", type=int)

    # ---------------------------------------
    # GET CHART DATA
    # ---------------------------------------
    chart_data = get_iptv_inventory_chart_data(weeks=selected_weeks)

    return render_template(
        "charts/iptv_users_dashboard.html",
        chart_data=chart_data,
        selected_weeks=selected_weeks,
    )


# GET REQUEST + query parameter FOR FILTERS
@chart_bp.route("/ont-charts", methods=["GET"])
@login_required
def ont_inventory_charts():
    # But still → submit GET params, GET + query parameter
    selected_id = request.args.get("id", type=int)

    selected_months = request.args.get("months", type=int)

    # ---------------------------------------
    # GET CHART DATA
    # ---------------------------------------
    chart_data = get_ont_inventory_chart_data(
        city_id=selected_id, months=selected_months
    )

    # ---------------------------------------
    # FOR LISTING IN HTML SELECT ELEMENTS
    # ---------------------------------------
    cities = get_distinct_joined_values(
        base_key="ont", join_key="city", base_fk="city_id"
    )

    # -----------------------------------
    # FOR BUILDING DYNAMIC TITLE IN CHART.JS
    # ---------------------------------------
    selected_city_name = None
    if selected_id:
        selected_city_name = next((c.name for c in cities if c.id == selected_id), None)

    return render_template(
        "charts/ont_dashboard.html",
        chart_data=chart_data,
        cities=cities,
        selected_id=selected_id,
        selected_city_name=selected_city_name,
        selected_months=selected_months,
    )


# GET REQUEST + query parameter FOR FILTERS
@chart_bp.route("/cpe-charts", methods=["GET"])
@login_required
def cpe_inventory_charts():
    selected_cpe_id = request.args.get("cpe_id", type=int)

    raw_cpe_type = request.args.get("cpe_type", type=str)

    if raw_cpe_type:
        try:
            selected_cpe_type = CpeTypeEnum(raw_cpe_type)
          
        except ValueError:
            selected_cpe_type = None
    else:
        selected_cpe_type = None

    # convert empty string ""  →  None
    if not selected_cpe_type:
        selected_cpe_type = None

    if not selected_cpe_type:
        selected_cpe_type = None

    # mutual exclusivity ON BACKEND
    if selected_cpe_id:
        selected_cpe_type = None

    selected_city_id = request.args.get("city_id", type=int)

    selected_weeks = request.args.get("weeks", type=int)

    # ---------------------------------------
    # GET CHART DATA
    # ---------------------------------------
    chart_data = get_cpe_inventory_chart_data(
        city_id=selected_city_id,
        cpe_id=selected_cpe_id,
        cpe_type=selected_cpe_type,
        weeks=selected_weeks,
    )

    # ---------------------------------------
    # FOR LISTING IN HTML SELECT ELEMENTS
    # ---------------------------------------
    # lists of cities in cpe_inventory
    cities = get_distinct_joined_values(
        base_key="cpe", join_key="city", base_fk="city_id"
    )

    # SHOW ONLY CPES THAT ARE ACTIVE IN TOTAL
    cpes = get_cpe_types_column_schema("visible_in_total", "order_in_total")

    # LIST OF CPE TYPES STRING NOT ENUMS
    cpe_types = sorted({cpe["cpe_type"] for cpe in cpes})

    # -----------------------------------
    # FOR BUILDING DYNAMIC TITLE IN CHART.JS
    # ---------------------------------------
    selected_cpe_name = None
    selected_city_name = None

    if selected_cpe_id:
        selected_cpe_name = next(
            (c["label"] for c in cpes if c["id"] == selected_cpe_id), None
        )

    if selected_city_id:
        selected_city_name = next(
            (c.name for c in cities if c.id == selected_city_id), None
        )

    return render_template(
        "charts/cpe_dashboard.html",
        chart_data=chart_data,
        cities=cities,
        cpes=cpes,
        types=cpe_types,
        selected_cpe_id=selected_cpe_id,
        selected_cpe_name=selected_cpe_name,
        selected_cpe_type=selected_cpe_type,
        selected_city_id=selected_city_id,
        selected_city_name=selected_city_name,
        selected_weeks=selected_weeks,
    )


# GET REQUEST + query parameter FOR FILTERS
@chart_bp.route("/cpe-dismantle-charts", methods=["GET"])
@login_required
def cpe_dismantle_inventory_charts():
    selected_city_id = request.args.get("city_id", type=int)

    selected_cpe_id = request.args.get("cpe_id", type=int)

    selected_cpe_type = request.args.get("cpe_type", type=str)

    # convert empty string ""  →  None
    if not selected_cpe_type:
        selected_cpe_type = None

    if not selected_cpe_type:
        selected_cpe_type = None

    # mutual exclusivity ON BACKEND
    if selected_cpe_id:
        selected_cpe_type = None

    selected_dismantle_id = request.args.get("dismantle_id", type=int)

    selected_weeks = request.args.get("weeks", type=int)

    # ---------------------------------------
    # GET CHART DATA
    # ---------------------------------------
    chart_data = get_cpe_dismantle_chart_data(
        city_id=selected_city_id,
        cpe_id=selected_cpe_id,
        cpe_type=selected_cpe_type,
        dismantle_type_id=selected_dismantle_id,
        weeks=selected_weeks,
    )

    # ---------------------------------------
    # FOR LISTING IN HTML SELECT ELEMENTS
    # ---------------------------------------
    # FOR DISMANTLE TABLE WE NEED TO QUERY ONLY IJ CITIES
    cities = get_distinct_joined_values(
        base_key="cpe_dis",
        join_key="city",
        base_fk="city_id",
        extra_joins="""
        LEFT JOIN cpe_types ct ON ct.id = b.cpe_type_id
        """,
        where_clause="AND j.type=:city_type",
        params={"city_type": CityTypeEnum.IJ.value},
    )

    dismantles = get_distinct_joined_values(
        base_key="cpe_dis", join_key="dis_type", base_fk="dismantle_type_id"
    )

    # SHOW ONLY CPES THAT ARE ACTIVE IN DISMANTLE
    cpes = get_cpe_types_column_schema("visible_in_dismantle", "order_in_dismantle")

    # LIST OF CPE TYPES STRING NOT ENUMS
    cpe_types = sorted({cpe["cpe_type"] for cpe in cpes})

    # -----------------------------------
    # FOR BUILDING DYNAMIC TITLE IN CHART.JS
    # ---------------------------------------
    selected_cpe_name = None
    selected_city_name = None
    selected_dismantle = None

    if selected_cpe_id:
        selected_cpe_name = next(
            (c["label"] for c in cpes if c["id"] == selected_cpe_id), None
        )

    if selected_dismantle_id:
        selected_dismantle = next(
            (d.label for d in dismantles if d.id == selected_dismantle_id), None
        )

    if selected_city_id:
        selected_city_name = next(
            (c.name for c in cities if c.id == selected_city_id), None
        )

    return render_template(
        "charts/cpe_dismantle_dashboard.html",
        chart_data=chart_data,
        cities=cities,
        cpes=cpes,
        types=cpe_types,
        dismantles=dismantles,
        selected_cpe_id=selected_cpe_id,
        selected_cpe_name=selected_cpe_name,
        selected_cpe_type=selected_cpe_type,
        selected_dismantle_id=selected_dismantle_id,
        selected_dismantle=selected_dismantle,
        selected_city_id=selected_city_id,
        selected_city_name=selected_city_name,
        selected_weeks=selected_weeks,
    )
