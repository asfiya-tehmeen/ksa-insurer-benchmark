"""Load the clean tables into DuckDB and create the SQL views in sql/.

    python -m src.build_db            -> data/clean/insurers.duckdb

Tables (all values SAR thousands unless a column says otherwise):
  statements_long     consolidated income statements, long (incl. page + method per value)
  milliman_long       Milliman exhibit tables (annual, whole company)
  segment_long        resolved segment values (medical / total) with source page
  panel_consolidated  whole-company ratios per insurer-period (older panel)
  panel_segment       insurer x period x segment panel with ratios
  milliman_medical_sector  Milliman sector medical table (SAR millions)
Views: sql/*.sql executed in filename order.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from .crosscheck import MILLIMAN_MEDICAL

DB = Path("data/clean/insurers.duckdb")
TABLES = {
    "statements_long": "data/clean/statements_long.csv",
    "milliman_long": "data/clean/milliman_long.csv",
    "segment_long": "data/clean/segment_long.csv",
    "panel_consolidated": "data/clean/panel.csv",
    "panel_segment": "data/clean/panel_segment.csv",
}


def build(db: Path = DB) -> duckdb.DuckDBPyConnection:
    if db.exists():
        db.unlink()
    con = duckdb.connect(str(db))
    for name, csv in TABLES.items():
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM read_csv_auto('{csv}', header=true)")
    con.register("_mm", MILLIMAN_MEDICAL)
    con.execute("CREATE TABLE milliman_medical_sector AS SELECT * FROM _mm")
    con.unregister("_mm")
    for f in sorted(Path("sql").glob("*.sql")):
        con.execute(f.read_text(encoding="utf-8"))
    return con


if __name__ == "__main__":
    con = build()
    for (v,) in con.execute("SELECT view_name FROM duckdb_views() WHERE NOT internal ORDER BY 1").fetchall():
        n = con.execute(f"SELECT COUNT(*) FROM {v}").fetchone()[0]
        print(f"{v:28s} {n:4d} rows")
