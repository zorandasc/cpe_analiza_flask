
# This approach bypasses the ORM's object mapping for this specific complex query,
# treating it purely as a data fetch, which is necessary when using custom database
# functions like crosstab.
def get_pivoted_data(schema_list: list):
    if not schema_list:
        # Return empty data lists immediately if no active CPE types are found
        return []

    # Extract ONLY the model names (the first element in the tuple)
    # This is what CROSSTAB uses for column names
    model_names = [item["name"] for item in schema_list]

    # for first select
    # Create the comma-separated list of model names (for the final SELECT)
    # e.g., 'p."H267N", p."Arris VIP4205/VIP4302/1113", ...'
    selected_columns = ", ".join([f'p."{name}"' for name in model_names])

    # for pivot table as
    # Create the comma-separated list of quoted model names (for the SQL)
    # e.g., '"H267N" int, "Arris VIP4205/VIP4302/1113" int, ...'
    quoted_columns = ", ".join([f'"{name}" int' for name in model_names])

    # for sum columns
    # To ensure your "UKUPNO" (Total) row always shows a number, use COALESCE
    sum_columns = ", ".join(
        [f'COALESCE(SUM("{name}"),0) AS "{name}"' for name in model_names]
    )

    # raw SQL statement, as crosstab isn't a standard, ORM-mappable function
    # Inject these lists into the complete SQL template
    SQL_QUERY = f"""
    WITH latest_pivot AS (
        SELECT
            C.NAME AS CITY_NAME, -- Add CITY_NAME here for final result
            P.CITY_ID, -- For ordering purposes
            {selected_columns}, -- COMMA separated list of columns
            MAX_TS.MAX_UPDATED_AT
        FROM
            (
                SELECT
                    *
                FROM
                    CROSSTAB (
                        $QUERY$
                        SELECT
                            R.CITY_ID,
                            S.NAME AS CPE_MODEL,
                            R.QUANTITY
                        FROM
                            (
                                SELECT
                                    CITY_ID,
                                    CPE_TYPE_ID,
                                    QUANTITY,
                                    UPDATED_AT,
                                    ROW_NUMBER() OVER (
                                        PARTITION BY CITY_ID, CPE_TYPE_ID
                                        ORDER BY UPDATED_AT DESC
                                    ) AS RN
                                FROM CPE_INVENTORY
                            ) AS R
                            JOIN CPE_TYPES S ON R.CPE_TYPE_ID = S.ID
                        WHERE RN = 1
                        ORDER BY R.CITY_ID
                        $QUERY$,
                        $CATEGORY$
                        SELECT NAME FROM CPE_TYPES WHERE NAME IN ({", ".join([f"'{name}'" for name in model_names])}) ORDER BY ID
                        $CATEGORY$
                    ) AS PIVOT_TABLE (
                        CITY_ID INTEGER,
                        {quoted_columns}
                    )
            ) AS P
            JOIN CITIES C ON C.ID = P.CITY_ID
            LEFT JOIN (
                SELECT
                    CITY_ID,
                    MAX(UPDATED_AT) AS MAX_UPDATED_AT
                FROM
                    CPE_INVENTORY
                GROUP BY
                    CITY_ID
            ) AS MAX_TS ON MAX_TS.CITY_ID = P.CITY_ID
        )
    
    -- Data Rows
    SELECT 
        CITY_ID, 
        CITY_NAME, 
        {selected_columns.replace("p.", "")}, -- Remove 'p.' alias as we are selecting directly from latest_pivot
        MAX_UPDATED_AT
    FROM latest_pivot

    UNION ALL

    -- Total Row
    SELECT 
        NULL::INTEGER AS CITY_ID,
        'UKUPNO'::VARCHAR AS CITY_NAME,
        {sum_columns},
        NULL::TIMESTAMP AS MAX_UPDATED_AT
    FROM latest_pivot 
    
    ORDER BY 
        CITY_ID ASC NULLS LAST; 
    """

    # 1. Prepare the raw SQL string
    # 2. Execute the query
    result = db.session.execute(text(SQL_QUERY))

    # 3. Fetch all rows
    # The result is a ResultProxy; .mappings() helps convert rows to dicts
    # for easier handling in a web app.
    return [row._asdict() for row in result.all()]





# The main difference with get_pivoted_data is that, for the history,
# you need to pivot on the updated_at timestamp
# and the cpe_model, while filtering for a single city_id
def get_history_city_cpe_invent(city_id: int, schema_list: list, page: int, per_page: int):
    """
    Retrieves the historical records for a specific city_id, pivoted by CPE type.
    This query handles pagination internally based on the unique UPDATED_AT timestamp.
    """
    if not schema_list:
        # Return empty data lists immediately if no active CPE types are found
        return []

    model_names = [item["name"] for item in schema_list]

    quoted_columns = ", ".join([f'"{name}" INT' for name in model_names])
    selected_columns = ", ".join([f'P."{name}"' for name in model_names])

    # koloko ima rows za izabrani grad
    # We need a separate query to get the total count for pagination
    count_query = text(
        f"""SELECT 
                COUNT(DISTINCT UPDATED_AT) 
            FROM CPE_INVENTORY 
            WHERE CITY_ID={city_id}"""
    )

    total_count = db.session.execute(count_query).scalar()

    # Calculate offset
    offset = (page - 1) * per_page

    # THIS IS THE QUERY FOR CROSSTAB FUNCTION
    # IT WILL FIND ALL PIVOTED DATAD (ROWS) FOR SELECTED CITY_ID
    inner_crosstab_query = f"""
    SELECT
        R.UPDATED_AT,
        S.NAME AS CPE_MODEL,
        R.QUANTITY
    FROM 
        CPE_INVENTORY R
    JOIN 
        CPE_TYPES S ON R.CPE_TYPE_ID=S.ID
    WHERE
        R.CITY_ID={city_id}
    ORDER BY
        R.UPDATED_AT DESC, S.NAME
    """

    # CRITICAL: We need to figure out which OF UPDATED_AT timestamps belong to the current page.
    # We do this using a subquery (distinct_updates) to find only the timestamps that are inside offset/limit.

    # 1.WE FIND ALL THE PIVOTED DATA IN CROSSTAB
    # 2. AND THEN JOIN WITH distinct_updates TABLE
    # distinct_updates TABLE ACT AS A FILTER.
    # IT HOLDS UPDATE_AT RECORDA LIMITED BY PAGE AN OFFSET
    # SO OUR FINAL PIVOTED DATA IS PAGINATED THROUGH FILTERING
    # PAGINATION ON ALL PIVOTED DATA IS NOT PERFORMANT
    SQL_QUERY = f"""
    WITH distinct_updates AS (
        SELECT DISTINCT UPDATED_AT
        FROM CPE_INVENTORY
        WHERE CITY_ID = {city_id}
        ORDER BY UPDATED_AT DESC
        LIMIT {per_page} OFFSET {offset}
    )
    SELECT
        D.UPDATED_AT,
        {selected_columns}
    FROM
        CROSSTAB (
            $QUERY$
            {inner_crosstab_query}
            $QUERY$,
            $CATEGORY$
            SELECT NAME FROM CPE_TYPES WHERE NAME IN ({", ".join([f"'{name}'" for name in model_names])}) ORDER BY ID
            $CATEGORY$
        ) AS P (
            UPDATED_AT TIMESTAMP,
            {quoted_columns}
        ) 
    JOIN
        distinct_updates D ON D.UPDATED_AT = P.UPDATED_AT
    ORDER BY
        P.UPDATED_AT DESC;
    """
    # The CROSSTAB generates a large pivoted table (P) containing all historical records for the city
    #  (row ID = UPDATED_AT).
    # The JOIN acts as a filter. It discards all rows from the massive
    # pivoted table (P) except for those whose UPDATED_AT timestamp matches one of the
    # handful of timestamps found in the small, already-paginated distinct_updates list (D).

    result = db.session.execute(text(SQL_QUERY))

    # pivoted_data is now list
    pivoted_data = [row._asdict() for row in result.all()]

    # paginate is iterable SimplePagination object
    paginate = SimplePagination(
        page=page, per_page=per_page, total=total_count, items=pivoted_data
    )

    return paginate

