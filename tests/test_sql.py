"""SQL views must agree with independent pandas calculations on the same panel."""
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from src.build_db import build

PANEL = Path("data/clean/panel_segment.csv")
pytestmark = pytest.mark.skipif(not PANEL.exists(), reason="run src.panel first")


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    db = tmp_path_factory.mktemp("db") / "t.duckdb"
    c = build(db)
    yield c
    c.close()


@pytest.fixture(scope="module")
def med():
    w = pd.read_csv(PANEL)
    return w[w.segment == "medical"].copy()


def test_medical_ratios_view_matches_panel(con, med):
    v = con.execute("SELECT insurer, period, loss_ratio, service_margin FROM v_medical_ratios").fetchdf()
    m = v.merge(med[["insurer", "period", "loss_ratio", "service_margin"]], on=["insurer", "period"], suffixes=("", "_p"))
    assert len(m) == len(med) == len(v)
    assert (m.loss_ratio - m.loss_ratio_p).abs().max() < 1e-12
    assert (m.service_margin - m.service_margin_p).abs().max() < 1e-12


def test_shares_sum_to_one_per_period(con):
    s = con.execute("SELECT period, SUM(share_of_benchmark_set) s FROM v_medical_market_share GROUP BY period").fetchdf()
    assert ((s.s - 1).abs() < 1e-9).all()


def test_share_of_sector_uses_milliman_in_millions(con):
    r = con.execute("""SELECT share_of_sector FROM v_medical_market_share
                       WHERE insurer='bupa' AND period='2024FY'""").fetchone()[0]
    bupa = pd.read_csv(PANEL).query("insurer=='bupa' and segment=='medical' and period=='2024FY'").revenue.iloc[0]
    assert r == pytest.approx(bupa / (40357 * 1000))      # Milliman p.15: 40,357 SAR m


def test_qoq_and_yoy_match_pandas(con, med):
    q = med[med.freq == "quarter"].copy()
    q["year"] = q.period.str[:4].astype(int)
    q["qn"] = q.period.str[5].astype(int)
    q["idx"] = q.year * 4 + q.qn
    key = q.set_index(["insurer", "idx"]).loss_ratio
    sql = con.execute("""SELECT insurer, period, loss_ratio_qoq_pp, loss_ratio_yoy_pp
                         FROM v_medical_changes WHERE freq='quarter'""").fetchdf()
    checked = 0
    for _, r in sql.iterrows():
        row = q[(q.insurer == r.insurer) & (q.period == r.period)].iloc[0]
        for lag, col in ((1, "loss_ratio_qoq_pp"), (4, "loss_ratio_yoy_pp")):
            prev = key.get((r.insurer, row.idx - lag))
            exp = None if prev is None else 100 * (row.loss_ratio - prev)
            if exp is None:
                assert pd.isna(r[col])
            else:
                assert r[col] == pytest.approx(exp, abs=1e-9)
                checked += 1
    assert checked > 30


def test_missing_quarter_gives_null_not_skipped_gap(con):
    # Tawuniya has no 2024Q4 -> 2025Q1 QoQ must be NULL (previous quarter absent)
    r = con.execute("""SELECT loss_ratio_qoq_pp FROM v_medical_changes
                       WHERE insurer='tawuniya' AND period='2025Q1'""").fetchone()[0]
    assert r is None or pd.isna(r)


def test_peer_rank_is_dense_from_one_and_ordered(con):
    d = con.execute("SELECT period, loss_ratio, loss_ratio_rank, n_peers FROM v_medical_peer_rank").fetchdf()
    for _, g in d.groupby("period"):
        assert g.loss_ratio_rank.min() == 1 and g.loss_ratio_rank.max() <= g.n_peers.iloc[0]
        g = g.sort_values("loss_ratio_rank")
        assert g.loss_ratio.is_monotonic_increasing
