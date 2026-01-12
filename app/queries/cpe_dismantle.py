from sqlalchemy import text
from app.extensions import db
from datetime import datetime
from app.utils.simplepagination import SimplePagination


def get_cpe_dismantle_pivoted(
    schema_list: list, week_end: datetime.date, city_type: str
):
    if not schema_list:
        # Return empty data lists immediately if no active CPE types are found
        return []

    case_columns = []
    sum_columns = []

    for model in schema_list:
        case_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN cpe_name = '{model["name"]}' THEN quantity END),
                0
            ) AS "{model["name"]}"
            """
        )
        sum_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN cpe_name = '{model["name"]}' THEN quantity END),
                0
            ) AS "{model["name"]}"
            """
        )

    SQL_QUERY = f"""
                WITH WEEKLY_DATA AS (
                SELECT
                    C.ID AS CITY_ID,
                    C.NAME AS CITY_NAME,
                    CT.NAME AS CPE_NAME,
                    CD.QUANTITY,
                    CD.DISMANTLE_TYPE_ID,
                    DT.CODE AS DISMANTLE_CODE,
                    CD.UPDATED_AT
                FROM CITIES C
                LEFT JOIN CPE_DISMANTLE CD
                    ON C.ID = CD.CITY_ID
                    AND CD.WEEK_END = (
                        SELECT MAX(CD2.WEEK_END)
                        FROM CPE_DISMANTLE CD2
                        WHERE CD2.CITY_ID = C.ID
                        AND CD2.WEEK_END <= :week_end
                )
                LEFT JOIN DISMANTLE_TYPES DT ON DT.ID = CD.DISMANTLE_TYPE_ID
                LEFT JOIN CPE_TYPES CT ON CT.ID = CD.CPE_TYPE_ID
                WHERE C.TYPE = :city_type
            )
            SELECT
                CITY_ID,
                CITY_NAME,
                DISMANTLE_TYPE_ID,
                DISMANTLE_CODE,
                {", ".join(case_columns)},
                MAX(updated_at) FILTER (
                WHERE dismantle_type_id = 1
                ) AS complete_updated_at,
                MAX(updated_at) FILTER (
                WHERE dismantle_type_id IN (2,3,4)
                ) AS missing_updated_at
            FROM WEEKLY_DATA
            GROUP BY CITY_ID, CITY_NAME, DISMANTLE_TYPE_ID,DISMANTLE_CODE

            UNION ALL

            SELECT
                NULL AS city_id,
                'UKUPNO' AS city_name,
                DISMANTLE_TYPE_ID,
                DISMANTLE_CODE,
                {", ".join(sum_columns)},
                NULL AS complete_updated_at,
                NULL AS missing_updated_at
            FROM WEEKLY_DATA
            GROUP BY DISMANTLE_TYPE_ID,DISMANTLE_CODE
            ORDER BY CITY_ID, DISMANTLE_TYPE_ID NULLS LAST;
    """

    params = {"week_end": week_end, "city_type": city_type}

    result = db.session.execute(text(SQL_QUERY), params)

    return [row._asdict() for row in result.all()]


def get_cpe_dismantle_city_history(
    city_id: int, schema_list: list, page: int, per_page: int
):
    if not schema_list:
        # Return empty data lists immediately if no active CPE types are found
        return []

    # We need a separate query to get the total count for pagination
    count_query = text(
        """SELECT 
                COUNT(DISTINCT WEEK_END) 
            FROM CPE_DISMANTLE
            WHERE CITY_ID=:city_id
        """
    )

    total_count = db.session.execute(count_query, {"city_id": city_id}).scalar()

    # Calculate offset
    offset = (page - 1) * per_page

    case_columns = []

    for model in schema_list:
        case_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN ct.name = '{model["name"]}' THEN cd.quantity END),
                0
            ) AS "{model["name"]}"
            """
        )

    SQL_QUERY = f"""
    SELECT
            WEEK_END,
            DT.CODE AS DISMANTLE_CODE,
            {", ".join(case_columns)}
        FROM cpe_dismantle cd
        JOIN DISMANTLE_TYPES DT ON DT.ID = CD.DISMANTLE_TYPE_ID
        LEFT JOIN cpe_types ct ON ct.id=cd.cpe_type_id
        WHERE cd.city_id = :city_id
        GROUP BY cd.WEEK_END, DISMANTLE_CODE
        ORDER BY cd.week_end DESC
        LIMIT :limit
        OFFSET :offset
    """

    params = {
        "city_id": city_id,
        "limit": per_page,
        "offset": offset,
    }

    result = db.session.execute(text(SQL_QUERY), params)

    # pivoted_data is now list
    pivoted_data = [row._asdict() for row in result.all()]

    # paginate is iterable SimplePagination object
    paginate = SimplePagination(
        page=page, per_page=per_page, total=total_count, items=pivoted_data
    )

    return paginate
