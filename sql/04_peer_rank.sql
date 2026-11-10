-- Peer rank per period among the insurers present in that period.
-- loss_ratio_rank: 1 = lowest medical loss ratio (best).  margin_rank: 1 = highest service margin.
-- n_peers differs by period (see v_medical_market_share.n_insurers_in_period): compare ranks only
-- between periods with the same n_peers.
CREATE OR REPLACE VIEW v_medical_peer_rank AS
SELECT
    insurer,
    period,
    freq,
    loss_ratio,
    service_margin,
    RANK() OVER (PARTITION BY period ORDER BY loss_ratio ASC)      AS loss_ratio_rank,
    RANK() OVER (PARTITION BY period ORDER BY service_margin DESC) AS margin_rank,
    COUNT(*) OVER (PARTITION BY period)                            AS n_peers,
    loss_ratio - AVG(loss_ratio) OVER (PARTITION BY period)        AS loss_ratio_vs_peer_avg
FROM v_medical_ratios;
