-- Quarter-on-quarter and year-on-year change in medical ratios (percentage points).
-- Joined on the exact previous period, so a missing quarter gives NULL, never a skipped-gap change.
-- Quarterly rows: QoQ vs previous quarter, YoY vs same quarter last year.
-- Annual rows:    YoY vs previous fiscal year (no QoQ).
CREATE OR REPLACE VIEW v_medical_changes AS
SELECT
    c.insurer,
    c.period,
    c.freq,
    c.loss_ratio,
    c.service_margin,
    100 * (c.loss_ratio     - q.loss_ratio)     AS loss_ratio_qoq_pp,
    100 * (c.loss_ratio     - y.loss_ratio)     AS loss_ratio_yoy_pp,
    100 * (c.service_margin - q.service_margin) AS service_margin_qoq_pp,
    100 * (c.service_margin - y.service_margin) AS service_margin_yoy_pp,
    c.revenue / NULLIF(y.revenue, 0) - 1        AS revenue_yoy_growth,
    c.is_derived OR COALESCE(q.is_derived, FALSE) OR COALESCE(y.is_derived, FALSE) AS uses_derived_q4
FROM v_medical_ratios c
LEFT JOIN v_medical_ratios q
       ON q.insurer = c.insurer AND c.freq = 'quarter' AND q.freq = 'quarter'
      AND q.year * 4 + q.quarter = c.year * 4 + c.quarter - 1
LEFT JOIN v_medical_ratios y
       ON y.insurer = c.insurer AND y.freq = c.freq AND y.year = c.year - 1
      AND COALESCE(y.quarter, 0) = COALESCE(c.quarter, 0);
