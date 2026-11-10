-- Medical-segment loss ratio, net service ratio and service margin per insurer and period,
-- with the WHOLE-COMPANY expense / combined ratio alongside (other operating expenses are
-- not allocated to segments by any insurer, so they exist only at total level).
--
-- loss_ratio        = insurance service expenses / insurance revenue   (gross of reinsurance;
--                     ISE includes claims AND directly attributable expenses - see README)
-- net_service_ratio = (ISE - net reinsurance result - pool surplus) / insurance revenue
-- service_margin    = insurance service result / insurance revenue  (= 1 - net_service_ratio)
CREATE OR REPLACE VIEW v_medical_ratios AS
SELECT
    m.insurer,
    m.period,
    m.freq,
    CAST(substr(m.period, 1, 4) AS INTEGER)                                     AS year,
    CASE WHEN m.freq = 'quarter' THEN CAST(substr(m.period, 6, 1) AS INTEGER) END AS quarter,
    m.revenue,
    m.claims                                                                    AS service_expenses,
    m.reinsurance_net,
    m.service_result,
    m.loss_ratio,
    m.net_service_ratio,
    m.service_margin,
    m.medical_share_of_revenue,
    t.loss_ratio            AS total_loss_ratio,
    t.expense_ratio_total   AS total_expense_ratio,
    t.combined_ratio_total  AS total_combined_ratio,
    m.post_ifrs17,
    m.mono_line,
    m.is_derived,
    m.source_files,
    m.source_pages
FROM panel_segment m
LEFT JOIN panel_segment t
       ON t.insurer = m.insurer AND t.period = m.period AND t.segment = 'total'
WHERE m.segment = 'medical';
