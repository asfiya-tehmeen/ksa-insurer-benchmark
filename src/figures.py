"""Two report figures -> reports/figures/. Run after src.analysis.

fig1_medical_vs_total.png   medical vs whole-company loss ratio per insurer (pooled 2024Q1-2025Q2)
fig2_quarterly_trend.png    quarterly medical loss ratio: constant 5-insurer group, Bupa, Tawuniya

Palette: validated reference categorical slots 1-3 (blue, orange, aqua); aqua is <3:1 on the light surface, so every
series is direct-labelled and the numbers are in reports/tables/*.csv. Ink is neutral, never the series colour.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

OUT = Path("reports/figures")
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "text.color": INK})


def base(figsize):
    fig, ax = plt.subplots(figsize=figsize, dpi=150, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    return fig, ax


def fig1():
    d = pd.read_csv("reports/tables/peer_comparison.csv").sort_values("medical_loss_ratio_pooled", ascending=False)
    fig, ax = base((8.6, 4.6))
    y = range(len(d))
    ax.axvline(1.0, color=INK2, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(1.004, -0.62, "100%", color=INK2, fontsize=8, va="center")
    for i, (_, r) in zip(y, d.iterrows()):
        ax.plot([r.total_loss_ratio_pooled, r.medical_loss_ratio_pooled], [i, i], color="#bdbcb6", linewidth=2, zorder=1)
        ax.scatter(r.total_loss_ratio_pooled, i, s=70, color=ORANGE, zorder=3, edgecolor=SURFACE, linewidth=1.5)
        ax.scatter(r.medical_loss_ratio_pooled, i, s=70, color=BLUE, zorder=3, edgecolor=SURFACE, linewidth=1.5)
        right = r.medical_loss_ratio_pooled >= r.total_loss_ratio_pooled
        ax.text(r.medical_loss_ratio_pooled + (0.012 if right else -0.012), i, f"{r.medical_loss_ratio_pooled:.0%}",
                ha="left" if right else "right", va="center", fontsize=8.5, color=INK)
        if r.medical_loss_ratio_pooled != r.total_loss_ratio_pooled:
            ax.text(r.total_loss_ratio_pooled + (-0.012 if right else 0.012), i, f"{r.total_loss_ratio_pooled:.0%}",
                    ha="right" if right else "left", va="center", fontsize=8.5, color=INK2)
    ax.set_yticks(list(y))
    ax.set_yticklabels([f"{n}  ({s:.0%} medical)" for n, s in zip(d.insurer, d.medical_share_of_revenue)], fontsize=9)
    ax.set_xlim(0.5, 1.3)
    ax.set_ylim(-0.9, len(d) - 0.4)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_xlabel("Insurance service expenses / insurance revenue (gross of reinsurance), pooled 2024Q1 to 2025Q2", fontsize=8.5)
    ax.scatter([], [], s=60, color=BLUE, label="Medical segment")
    ax.scatter([], [], s=60, color=ORANGE, label="Whole company")
    ax.legend(frameon=False, fontsize=8.5, loc="upper right")
    ax.set_title("Medical loss ratios re-rank the insurers:\nwhole-company figures mislead for multi-line carriers",
                 fontsize=10.5, loc="left", color=INK, pad=10)
    fig.tight_layout()
    fig.savefig(OUT / "fig1_medical_vs_total.png", facecolor=SURFACE)


def fig2():
    t = pd.read_csv("reports/tables/fixed_group_trend.csv")
    p = pd.read_csv("data/clean/panel_segment.csv")
    p = p[(p.segment == "medical") & (p.freq == "quarter")]
    order = [f"{y}Q{k}" for y in (2023, 2024, 2025) for k in (1, 2, 3, 4)]
    pos = {q: i for i, q in enumerate(order)}
    fig, ax = base((8.6, 4.4))
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.grid(axis="x", visible=False)
    ax.axhline(1.0, color=INK2, linewidth=1, linestyle=(0, (4, 3)))
    series = [("5-insurer group*", t.assign(derived=t.has_derived).rename(columns={"period": "p"})[["p", "loss_ratio", "derived"]], BLUE)]
    for key, label, col in (("bupa", "Bupa Arabia", ORANGE), ("tawuniya", "Tawuniya", AQUA)):
        g = p[p.insurer == key]
        series.append((label, pd.DataFrame({"p": g.period, "loss_ratio": g.loss_ratio, "derived": g.is_derived}), col))
    for label, g, col in series:
        g = g.assign(x=g.p.map(pos)).sort_values("x")
        ax.plot(g.x, g.loss_ratio, color=col, linewidth=2, zorder=2)
        for _, r in g.iterrows():
            ax.scatter(r.x, r.loss_ratio, s=44, zorder=3, color=SURFACE if r.derived else col,
                       edgecolor=col, linewidth=2)
        last = g.iloc[-1]
        dy = -0.014 if label == "Tawuniya" else 0
        ax.text(last.x + 0.15, last.loss_ratio + dy, f"{label}  {last.loss_ratio:.0%}", va="center", fontsize=8.5, color=INK)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([q.replace("Q", "\nQ") if q.endswith("Q1") else q[4:] for q in order], fontsize=8)
    ax.set_xlim(-0.4, len(order) + 2.9)
    ax.set_ylim(0.78, 1.14)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.set_ylabel("Medical insurance service expenses / revenue", fontsize=8.5)
    ax.set_title("Medical loss ratio by quarter: improvement into 2025 for the five-insurer group",
                 fontsize=10.5, loc="left", color=INK, pad=12)
    fig.text(0.01, 0.012, "Hollow markers = Q4 derived as FY minus 9M (not a filed quarter).  100% = break-even before reinsurance.\n"
             "*Al Rajhi Takaful, GIG, Malath, Medgulf, Walaa pooled (constant composition). Bupa has no 2025 Q3/Q4; Tawuniya has no Q4.",
             fontsize=7, color=INK2, va="bottom")
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(OUT / "fig2_quarterly_trend.png", facecolor=SURFACE)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fig1()
    fig2()
    print("saved to", OUT)
