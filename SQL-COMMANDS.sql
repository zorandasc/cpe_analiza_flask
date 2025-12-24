
-- FOR CROSSTABLE FUNCIONALITY IN SQL
CREATE EXTENSION IF NOT EXISTS tablefunc;


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
	DISMANTLE_TYPES (ID, LABEL, DESCRIPTION)
VALUES
	(1, 'COMP', 'Kompletna demontaža'),
	(2, 'ND', 'Nema daljinski'),
	(3, 'NA', 'Nema adapter'),
	(4, 'NDIA', 'Nema daljinski i adapter')


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
LIMIT 300;

--  ONT_INVENTORY------------------------------------
--In PostgreSQL, the most reliable way to get the 
--"last day of the month" is to add one month to the start of a month 
--and then subtract one day.
--date_trunc('month', ...) finds the first day of the month.
--+ interval '1 month' jumps to the first day of the next month.
--- interval '1 day' rolls it back to the last day of the intended month.

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
        d.last_day as month_end
    FROM 
        -- 1. City IDs from 3 to 11
        generate_series(3, 11) AS c(id)
    CROSS JOIN (
        -- 2. Generate the last day of each month for 2025
        SELECT (date_trunc('month', '2025-01-01'::date + (m || ' month')::interval) 
                + interval '1 month' - interval '1 day')::date as last_day
        FROM generate_series(0, 11) m
    ) d
) sub
ORDER BY RANDOM() 
LIMIT 300;