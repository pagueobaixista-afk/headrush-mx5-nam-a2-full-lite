"""Gera docs/nam-a2-full-lite-v3.png (README). Dados: tabela do README (comparacao/run.sh) e medições no aparelho."""
import os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

S, I, I2, G = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, LIGHT, GREY, REF = "#2a78d6", "#86b6ef", "#b4b2a9", "#8a8984"

# residual (dB) dos 4 modelos A2 da tabela -> % da energia do som que difere do oficial
lite_db = [-24.6, -26.5, -22.7, -16.1]
lite_pct = [100 * 10 ** (d / 10) for d in lite_db]
lo, hi, avg = min(lite_pct), max(lite_pct), sum(lite_pct) / len(lite_pct)

plt.rcParams.update({"font.family": "Segoe UI", "font.size": 11})
fig, (a, b) = plt.subplots(1, 2, figsize=(12.5, 4.4), dpi=150)
fig.patch.set_facecolor(S)
for ax in (a, b):
    ax.set_facecolor(S); ax.grid(axis="x", color=G, zorder=0); ax.tick_params(length=0, colors=I2)
    [s.set_visible(False) for s in ax.spines.values()]

# 1) diferença de som
rows = [("TONE3000 official NAM", 0, REF, "0%  (reference)"),
        ("MX5 Full (this mod)", 0, BLUE, "0%  identical sound"),
        ("MX5 Lite (this mod and lolgab v0.1.6)", avg, LIGHT, f"{avg:.1f}% on average ({lo:.1f}–{hi:.1f}%)")]
for y, (lab, v, c, txt) in zip(range(len(rows))[::-1], rows):
    a.barh(y, max(v, 0.02), height=0.55, color=c, zorder=2)
    a.text(max(v, 0.02) + 0.06, y, txt, va="center", color=I, fontsize=10.5, fontweight="bold")
a.set_yticks(range(len(rows))[::-1]); a.set_yticklabels([r[0] for r in rows], color=I)
a.set_xlim(0, 3); a.set_xticks([0, 1, 2, 3]); a.set_xticklabels(["0%", "1%", "2%", "3%"])
a.set_title("How different the sound is from official NAM\n(lower = closer; same input, 4 A2 bass models)",
            loc="left", color=I, fontweight="bold", fontsize=11.5)

# 2) uso do processador
rows = [("Full, lolgab v0.1.6\n(over its 50% limit: plays Lite)", 71.5, GREY, "72%"),
        ("Full, this mod", 45.1, BLUE, "45%  runs live"),
        ("Lite, lolgab v0.1.6", 10.8, GREY, "11%"),
        ("Lite, this mod", 7.3, LIGHT, "7%")]
for y, (lab, v, c, txt) in zip(range(len(rows))[::-1], rows):
    b.barh(y, v, height=0.55, color=c, zorder=2)
    b.text(v + 1.5, y, txt, va="center", color=I, fontsize=10.5, fontweight="bold")
b.axvline(100, color=I2, lw=1, ls="--"); b.text(99, -0.45, "100% = no time left", ha="right", color=I2, fontsize=9)
b.set_yticks(range(len(rows))[::-1]); b.set_yticklabels([r[0] for r in rows], color=I)
b.set_xlim(0, 112); b.set_xticks([0, 25, 50, 75, 100]); b.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])
b.set_title("How much of the MX5's audio time NAM uses\n(lower = more room for other effects)",
            loc="left", color=I, fontweight="bold", fontsize=11.5)

fig.tight_layout(w_pad=3)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "nam-a2-full-lite-v3.png")
fig.savefig(out, facecolor=S); print("ok", out)
