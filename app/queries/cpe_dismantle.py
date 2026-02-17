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
                    AND c.is_active = true
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
    city_id: int, schema_list: list, list_of_dismantles: list, page: int, per_page: int
):
    if not schema_list:
        # Return empty data lists immediately if no active CPE types are found
        return []

    # We need a separate query to get the total count for pagination
    count_query = text(
        """SELECT COUNT(*) FROM (
            SELECT cd.week_end, dt.code
            FROM cpe_dismantle cd
            JOIN dismantle_types dt ON dt.id = cd.dismantle_type_id
            WHERE cd.city_id = :city_id
            AND cd.dismantle_type_id IN :d_list
            GROUP BY cd.week_end, dt.code
        ) t
        """
    )

    total_count = db.session.execute(
        count_query,
        {
            "city_id": city_id,
            "d_list": tuple(list_of_dismantles),
        },
    ).scalar()

    # Calculate offset
    offset = (page - 1) * per_page

    # case_columns is actualy at building list of sql statements:
    # [SUM(CASE WHEN ct.id = :{place_holder} THEN cd.quantity END), ....]
    case_columns = []

    params = {
        "city_id": city_id,
        "limit": per_page,
        "offset": offset,
        "d_list": tuple(list_of_dismantles),
    }

    for i, model in enumerate(schema_list):
        place_holder = f"cpe_{i}"
        # build list of sql statement with parameterized values
        # this statement with injected values will be exsecutet at the end
        # with result = db.session.execute(text(SQL_QUERY), params)
        case_columns.append(
            f"""
            COALESCE(
                SUM(CASE WHEN ct.id = :{place_holder} THEN cd.quantity END),
                0
            ) AS "{model["name"]}"
            """
        )
        # this will fill params object with: cpe_1= model[1], cpe_2=model[2],..
        params[place_holder] = model["id"]

    SQL_QUERY = f"""
        SELECT
            WEEK_END,
            DT.CODE AS DISMANTLE_CODE,
            {", ".join(case_columns)}
        FROM cpe_dismantle cd
        JOIN DISMANTLE_TYPES DT ON DT.ID = CD.DISMANTLE_TYPE_ID
        LEFT JOIN cpe_types ct ON ct.id=cd.cpe_type_id
        WHERE cd.city_id = :city_id
        AND dismantle_type_id IN :d_list
        GROUP BY cd.WEEK_END,DT.CODE
        ORDER BY cd.week_end DESC
        LIMIT :limit
        OFFSET :offset
    """

    # this when all the params will be injected
    result = db.session.execute(text(SQL_QUERY), params)

    # pivoted_data is now list
    pivoted_data = [row._asdict() for row in result.all()]

    # paginate is iterable SimplePagination object
    paginate = SimplePagination(
        page=page, per_page=per_page, total=total_count, items=pivoted_data
    )

    return paginate
