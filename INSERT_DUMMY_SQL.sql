
-- FOR ENABLING CROSSTABLE FUNCIONALITY IN SQL
CREATE EXTENSION IF NOT EXISTS tablefunc;

--This usually happens when PostgreSQL's sequence (the counter it uses to generate
-- the next unique ID) is out of sync with the highest id currently in your table.
--You need to manually tell PostgreSQL to look at the maximum existing id in your cities
--setval('cities_id_seq', ...): Resets the internal counter of the sequence named 
--cities_id_seq to that maximum value
SELECT setval('cities_id_seq', (SELECT MAX(id) FROM cities));

-- FOR CITIES--------------
INSERT INTO
	CITIES (ID, NAME, TYPE)
VALUES
	(1, 'Centralno skladište', 'SKLADISTE'),
	(2, 'Skladište servisirane opreme', 'SKLADISTE'),
	(3, 'IJ Banja Luka', 'IJ'),
	(4, 'IJ Prijedor', 'IJ'),
	(5, 'IJ Doboj', 'IJ'),
	(6, 'IJ Bijeljina', 'IJ'),
	(7, 'IJ Brčko', 'IJ'),
    (8, 'IJ Zvornik', 'IJ'),
	(9, 'IJ I.Sarajevo', 'IJ'),
	(10, 'IJ Foča', 'IJ'),
	(11, 'IJ Trebinje', 'IJ'),
	(12, 'Posrednička skladišta DTH', 'SKLADISTE'),
	(13, 'Raspoloživa oprema', 'SKLADISTE')
	

-- FOR DISMANTLE_TYPES------------------------------------
INSERT INTO
	DISMANTLE_TYPES (ID, CODE, LABEL, GROUP_NAME)
VALUES
	(1, 'COMP', 'Kompletna demontaža', 'complete'),
	(2, 'ND', 'Nema daljinski', 'missing_parts'),
	(3, 'NA', 'Nema adapter', 'missing_parts'),
	(4, 'NDIA', 'Nema daljinski i adapter', 'missing_parts')


-- FOR STB_TYPES------------------------------------
INSERT INTO
	STB_TYPES (ID, NAME, LABEL)
VALUES
	(1, 'AMI139', 'Amino 139'),
	(2, 'VIP4302', 'VIP 4302'),
	(3, 'VIP1113', 'Arris VIP1113'),
	(4, 'VIP1113W', 'Arris VIP1113W'),
	(5, 'VIP4205', 'VIP 4205'),
	(6, 'EKT7005v', 'EKT 7005v HD'),
	(7, 'EKT4805v', 'EKT 4805v 4K'),
	(8, 'VIP5305', 'VIP5305'),
	(9, 'HP44P', 'Strong HP44P')



-- FOR CPE_TYPES------------------------------------
INSERT INTO
	CPE_TYPES (ID, NAME, LABEL, TYPE)
VALUES
	(
		1,
		'iads',
		'IAD-a H267N / HG658V2 / Zyxel /Skyworth',
		'IAD'
	),
	(
		2,
		'VIP4205_VIP4302_1113',
		'STB-ova Arris VIP4205/VIP4302/1113',
		'STB'
	),
	(
		3,
		'VIP5305',
		'STB-ova Arris VIP5305',
		'STB'
	),
	(
		4,
		'DIN4805V',
		'STB-ova EKT DIN4805V 4K',
		'STB'
	),
	(
		5,
		'DIN7005V',
		'STB-ova EKT DIN7005V HD',
		'STB'
	),
	(
		6,
		'HP44H',
		'Skyworth STBHD/4K HP44H',
		'STB'
	),
	(
		7,
		'ONT_HUA',
		'ONT (HUAWEI)',
		'ONT'
	),
	(
		8,
		'ONT_NOK',
		'ONT (NOKIA)',
		'ONT'
	),
	(
		9,
		'STB_DTH',
		'UREĐAJ STB DTH',
		'STB_DTH'
	),
	(
		10,
		'ANT_SAT_DTH',
		'ANTENA SATELITSKA DTH',
		'ANTENA'
	),
	(
		11,
		'LNB_DUO_TWIN',
		'LNB DUO TWIN',
		'LNB'
	)


--  STB_INVENTORY------------------------------------


INSERT INTO stb_inventory (
    stb_type_id, 
    week_end, 
    quantity,
    created_at, 
    updated_at
)
SELECT 
    sub.stb_type_id, 
    sub.week_end, 
    (FLOOR(RANDOM() * 100) + 1)::INT,
    NOW(), 
    NOW()
FROM (
    SELECT 
        t.type_id as stb_type_id, 
        d.date_val as week_end
    FROM 
        generate_series(1, 9) AS t(type_id)
    CROSS JOIN (
        -- Generate dates and filter for Fridays (DOW = 5)
        SELECT ('2025-01-01'::DATE + i) as date_val
        FROM generate_series(0, 333) i
        WHERE EXTRACT(DOW FROM ('2025-01-01'::DATE + i)) = 5
    ) d
) sub
ORDER BY RANDOM() 
LIMIT 600;

--  ONT_INVENTORY------------------------------------
--In PostgreSQL, the most reliable way to get the 
--"last day of the month" is to add one month to the start of a month 
--and then subtract one day.
--date_trunc('month', ...) finds the first day of the month.
--+ interval '1 month' jumps to the first day of the next month.
--- interval '1 day' rolls it back to the last day of the intended month.


-- Dynamic Range: I replaced the static '2022-01-01' with NOW() - interval '5 years'. 
--This ensures your query always looks back exactly 5 years from the day you run it.

-- Generate Series by Interval: Instead of generating numbers (0–11) and adding them to a date, 
--Postgres allows you to generate a series directly using intervals (e.g., '1 month'). 
--This is cleaner and handles year transitions automatically.

--Month-End Logic: The logic date_trunc('month', ...) + interval '1 month - 1 day' 
--is a standard Postgres "trick" to find the last day of any given month.



INSERT INTO ont_inventory (
    city_id, 
    month_end, 
    quantity,
    created_at, 
    updated_at
)
SELECT 
    sub.city_id, 
    sub.month_end, 
    (FLOOR(RANDOM() * 100) + 1)::INT,
    NOW(), 
    NOW()
FROM (
    SELECT 
        c.id as city_id, 
        -- Calculates the last day of the month for each date in the series
        (date_trunc('month', d.month_date) + interval '1 month - 1 day')::date as month_end
    FROM 
        generate_series(3, 11) AS c(id)
    CROSS JOIN (
        -- Generates a series of dates from 5 years ago to today, stepping by 1 month
        SELECT generate_series(
            date_trunc('month', NOW() - interval '5 years'), 
            date_trunc('month', NOW()), 
            '1 month'::interval
        ) AS month_date
    ) d
) sub
ORDER BY RANDOM() 
LIMIT 600;


--A CROSS JOIN (also known as a Cartesian Product) is the most "aggressive" way 
--to join tables. Unlike a regular join where you look for matching IDs, 
--a Cross Join tells the database: "Take every single row from Table A 
--and pair it with every single row from Table B."


--NEW CPE_INVENTORY---------------
--Do not randomize identity (city, cpe, week)
--✔ Randomize only quantity
--✔ Let uniqueness enforce correctness
--✔ Dummy data should look like real business data
INSERT INTO
    CPE_INVENTORY (
        CITY_ID,
        CPE_TYPE_ID,
        QUANTITY,
        WEEK_END,
        CREATED_AT,
        UPDATED_AT
    )
SELECT
    C.ID AS CITY_ID,
    T.ID AS CPE_TYPE_ID,
    (FLOOR(RANDOM() * 500) + 1)::INT AS QUANTITY,
    F.FRIDAY_DATE AS WEEK_END,
    F.FRIDAY_DATE AS CREATED_AT,
    F.FRIDAY_DATE AS UPDATED_AT
FROM
    CITIES C
    CROSS JOIN CPE_TYPES T
    CROSS JOIN (
        -- Generates the last 80 Fridays
        SELECT
            (
                DATE_TRUNC('week', NOW()) + INTERVAL '4 days' - (W || ' weeks')::INTERVAL
            )::DATE AS FRIDAY_DATE
        FROM
            GENERATE_SERIES(1, 79) AS W
    ) AS F;


--CPE_DISMANTLE_INVENTORY---------------
INSERT INTO
	CPE_DISMANTLE (
		CITY_ID,
		CPE_TYPE_ID,
		DISMANTLE_TYPE_ID,
		QUANTITY,
		WEEK_END,
		CREATED_AT,
		UPDATED_AT
	)
SELECT
	C.ID AS CITY_ID,
	T.ID AS CPE_TYPE_ID,
	D.ID AS DISMANTLE_TYPE_ID,
	(FLOOR(RANDOM() * 500) + 1)::INT AS QUANTITY,
	F.FRIDAY_DATE AS WEEK_END,
	F.FRIDAY_DATE AS CREATED_AT,
	F.FRIDAY_DATE AS UPDATED_AT
FROM
	CITIES C
	CROSS JOIN CPE_TYPES T
	CROSS JOIN DISMANTLE_TYPES D
	CROSS JOIN (
		-- last 4 completed Fridays
		SELECT
			(
				DATE_TRUNC('week', NOW()) + INTERVAL '4 days' - (W || ' weeks')::INTERVAL
			)::DATE AS FRIDAY_DATE
		FROM
			GENERATE_SERIES(1, 60) AS W
	) AS F;



INSERT INTO
	IPTV_USERS (TOTAL_USERS, WEEK_END, CREATED_AT,UPDATED_AT)
SELECT
	(FLOOR(RANDOM() * 1000) + 1)::INT,
	DATE_VAL,
	DATE_VAL,
	DATE_VAL
FROM(
		-- Generate dates and filter for Fridays (DOW = 5)
		SELECT
			('2025-01-01'::DATE + I) AS DATE_VAL
		FROM
			GENERATE_SERIES(0, 333) I
		WHERE
			EXTRACT(
				DOW
				FROM
					('2025-01-01'::DATE + I)
			) = 5)
ORDER BY
	RANDOM()
LIMIT
	600