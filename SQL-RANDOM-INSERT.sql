
-- FOR CROSSTABLE FUNCIONALITY IN SQL
CREATE EXTENSION IF NOT EXISTS tablefunc;


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
    -- quantity: Random integer between 1 and 100
    (FLOOR(RANDOM() * 100) + 1)::INT,
    NOW(), 
    NOW()
FROM (
    -- Pool of unique stb_type_id and week_end combinations
    SELECT 
        t.type_id as stb_type_id, 
        ('2025-01-01'::DATE + (d.day)::INT) as week_end
    FROM 
        generate_series(1, 9) AS t(type_id)
    CROSS JOIN 
        generate_series(0, 333) AS d(day)
) sub
ORDER BY RANDOM() 
LIMIT 300;