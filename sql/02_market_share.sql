-- Share of MEDICAL insurance revenue.
-- share_of_benchmark_set: share among the insurers that have a value in that period
--   (n_insurers_in_period says how many; compare shares only where n is the same).
-- share_of_sector (annual only): our insurer's medical revenue / Milliman sector medical revenue.
CREATE OR REPLACE VIEW v_medical_market_share AS
SELECT
    r.insurer,
    r.period,
    r.freq,
    r.revenue,
    r.revenue / SUM(r.revenue) OVER (PARTITION BY r.period)  AS share_of_benchmark_set,
    COUNT(*)  OVER (PARTITION BY r.period)                   AS n_insurers_in_period,
    CASE WHEN r.freq = 'annual'
         THEN r.revenue / (s.revenue * 1000.0) END           AS share_of_sector
FROM v_medical_ratios r
LEFT JOIN milliman_medical_sector s ON s.period = r.period AND r.freq = 'annual';
