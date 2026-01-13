from sqlalchemy import text
from app.extensions import db


# cpe inventory
def get_cpe_inventory_chart_data(city_id=None, cpe_type_id=None, weeks=None):
    params = {}
    conditions = []

    if city_id is not None:
        conditions.append("city_id = :city_id")
        params["city_id"] = city_id

    if cpe_type_id is not None:
        conditions.append("cpe_type_id = :cpe_type_id")
        params["cpe_type_id"] = cpe_type_id

    where_clause = ""
    if conditions:
        where_clause = " AND " + " AND ".join(conditions)

    if weeks:
        sql = f"""
            WITH last_weeks AS (
                SELECT DISTINCT week_end
                FROM cpe_inventory
                WHERE 1=1 {where_clause}
                ORDER BY week_end DESC
                LIMIT :weeks
            )
            SELECT i.week_end, SUM(i.quantity) AS total
            FROM cpe_inventory i
            JOIN last_weeks w ON w.week_end = i.week_end
            WHERE 1=1 {where_clause}
            GROUP BY i.week_end
            ORDER BY i.week_end
        """
        params["weeks"] = weeks
    else:
        sql = f"""
            SELECT week_end, SUM(quantity) AS total
            FROM cpe_inventory
            WHERE 1=1 {where_clause}
            GROUP BY week_end
            ORDER BY week_end
        """

    rows = db.session.execute(text(sql), params).fetchall()

    return {
        "labels": [r.week_end.strftime("%Y-%m-%d") for r in rows],
        "data": [r.total for r in rows],
    }


def get_cpe_within_cpe_inventory():
    return db.session.execute(
        text(
            """
        SELECT DISTINCT t.id, t.label
        FROM cpe_inventory i
        JOIN cpe_types t ON t.id = i.cpe_type_id
        ORDER BY t.id
        """
        )
    ).fetchall()


def get_cities_within_cpe_inventory():
    return db.session.execute(
        text(
            """
            SELECT DISTINCT c.id, c.name
            FROM cpe_inventory i
            JOIN cities c ON c.id = i.city_id
            ORDER BY c.id
        """
        )
    ).fetchall()


# cpe dismantles
def get_cpe__dismantle_inventory_chart_data(
    city_id=None, cpe_type_id=None, dismantle_type_id=None, weeks=None
):
    params = {}
    conditions = []

    if city_id is not None:
        conditions.append("city_id = :city_id")
        params["city_id"] = city_id

    if cpe_type_id is not None:
        conditions.append("cpe_type_id = :cpe_type_id")
        params["cpe_type_id"] = cpe_type_id

    if dismantle_type_id is not None:
        conditions.append("dismantle_type_id = :dismantle_type_id")
        params["dismantle_type_id"] = dismantle_type_id

    where_clause = ""
    if conditions:
        where_clause = " AND " + " AND ".join(conditions)

    if weeks:
        sql = f"""
            WITH last_weeks AS (
                SELECT DISTINCT week_end
                FROM cpe_dismantle
                WHERE 1=1 {where_clause}
                ORDER BY week_end DESC
                LIMIT :weeks
            )
            SELECT i.week_end, SUM(i.quantity) AS total
            FROM cpe_dismantle i
            JOIN last_weeks w ON w.week_end = i.week_end
            WHERE 1=1 {where_clause}
            GROUP BY i.week_end
            ORDER BY i.week_end
        """
        params["weeks"] = weeks
    else:
        sql = f"""
            SELECT week_end, SUM(quantity) AS total
            FROM cpe_dismantle
            WHERE 1=1 {where_clause}
            GROUP BY week_end
            ORDER BY week_end
        """

    rows = db.session.execute(text(sql), params).fetchall()

    return {
        "labels": [r.week_end.strftime("%Y-%m-%d") for r in rows],
        "data": [r.total for r in rows],
    }


def get_cpe_within_cpe_dismantle_inventory():
    return db.session.execute(
        text(
            """
        SELECT DISTINCT t.id, t.label
        FROM cpe_dismantle i
        JOIN cpe_types t ON t.id = i.cpe_type_id
        ORDER BY t.id
        """
        )
    ).fetchall()


def get_cities_within_cpe_dismantle_inventory():
    return db.session.execute(
        text(
            """
            SELECT DISTINCT c.id, c.name
            FROM cpe_dismantle i
            JOIN cities c ON c.id = i.city_id
            ORDER BY c.id
        """
        )
    ).fetchall()


def get_dismantles_within_cpe_dismantle_inventory():
    return db.session.execute(
        text(
            """
        SELECT DISTINCT t.id, t.label
        FROM cpe_dismantle i
        JOIN dismantle_types t ON t.id = i.dismantle_type_id
        ORDER BY t.id
        """
        )
    ).fetchall()


# stb inventory
def get_stb_inventory_chart_data(stb_type_id=None, weeks=None):
    params = {}

    where = ""
    if stb_type_id:
        where = "AND stb_type_id= :stb_type_id"
        params["stb_type_id"] = stb_type_id

    if weeks:
        sql = f"""
        WITH last_week AS (
        SELECT DISTINCT week_end
        FROM stb_inventory 
        WHERE 1=1 {where}
        ORDER BY week_end DESC
        LIMIT :weeks
        )
        SELECT i.week_end, SUM(i.quantity) AS total
        FROM stb_inventory i
        JOIN last_week w ON w.week_end=i.week_end
        WHERE 1=1 {where}
        GROUP BY i.week_end
        ORDER BY i.week_end
        """
        params["weeks"] = weeks
    else:
        sql = f"""
        SELECT week_end, SUM(quantity) AS total
        FROM stb_inventory
        WHERE 1=1 {where}
        GROUP BY week_end
        ORDER BY week_end
        """

    rows = db.session.execute(text(sql), params).fetchall()

    return {
        "labels": [r.week_end.strftime("%Y-%m-%d") for r in rows],
        "data": [r.total for r in rows],
    }


def get_stb_within_stb_inventory():
    return db.session.execute(
        text(
            """
        SELECT DISTINCT t.id, t.label
        FROM stb_inventory i
        JOIN stb_types t ON t.id = i.stb_type_id
        ORDER BY t.id
        """
        )
    ).fetchall()


# ont inventory
def get_ont_inventory_chart_data(city_id=None, months=None):
    params = {}

    where = ""
    if city_id:
        where = "AND city_id= :city_id"
        params["city_id"] = city_id

    if months:
        sql = f"""
        WITH last_month AS (
        SELECT DISTINCT month_end
        FROM ont_inventory 
        WHERE 1=1 {where}
        ORDER BY month_end DESC
        LIMIT :months
        )
        SELECT i.month_end, SUM(i.quantity) AS total
        FROM ont_inventory i
        JOIN last_month m ON m.month_end=i.month_end
        WHERE 1=1 {where}
        GROUP BY i.month_end
        ORDER BY i.month_end
        """
        params["months"] = months
    else:
        sql = f"""
        SELECT month_end, SUM(quantity) AS total
        FROM ont_inventory
        WHERE 1=1 {where}
        GROUP BY month_end
        ORDER BY month_end
        """

    rows = db.session.execute(text(sql), params).fetchall()

    return {
        "labels": [r.month_end.strftime("%Y-%m-%d") for r in rows],
        "data": [r.total for r in rows],
    }


def get_cities_within_ont_inventory():
    return db.session.execute(
        text(
            """
            SELECT DISTINCT c.id, c.name
            FROM ont_inventory i
            JOIN cities c ON c.id = i.city_id
            ORDER BY c.id
        """
        )
    ).fetchall()
