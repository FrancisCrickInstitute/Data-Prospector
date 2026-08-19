# -*- coding: utf-8 -*-
"""Generates the pipeline overview figure used at the top of README.md.

A from-scratch matplotlib illustration (no external icon libraries/network calls, so it's
reproducible offline) in the visual grammar of a journal graphical abstract: numbered stage
panels, simple flat icons, a fan-out that stays plural all the way to the output (it's a "diverger",
not a "converger" - see DIVERGER_PLAN.md §1): many independent ideas branch out, most are kept only
as a shortlist, and the few that are tested each run through their own parallel build lane.

Run with: pixi run python assets/generate_pipeline_figure.py
Writes: assets/pipeline_diagram.svg (embedded in README.md) and .png (quick local preview).
"""

import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle

# --- Palette: flat, muted, print-safe - one color per pipeline stage, plus a shared ink/paper pair.
INK = "#2B2D34"
PAPER = "#FFFFFF"
MUTED = "#9A9FA8"
INPUT_C = "#2E7D6B"        # teal - the material you bring
IDEATE_C = "#D9A02C"       # amber - many independent sparks
JUDGE_C = "#6C5B9E"        # violet - scored/weighed
REALISE_C = "#C1622D"      # burnt orange - built and safety-tested
CONFIRMED_C = "#3E8B5C"    # green
DISCONFIRMED_C = "#3D6FB4"  # blue
INCONCLUSIVE_C = "#9AA0AC"  # gray
NOT_REALISABLE_C = "#B08968"  # muted tan - "couldn't be built" (an engineering/provisioning gap)

TITLE_Y_OFFSET = 3.05
CAPTION_Y_OFFSET = 2.55


def stage_label(ax, x, y_base, number, title, caption, char_w=0.14):
    """Numbered circle + bold title, auto-centered as a block over x; caption below, also centered."""
    title_w = char_w * len(title)
    circle_x = x - title_w / 2 - 0.24
    y = y_base + TITLE_Y_OFFSET
    ax.add_patch(Circle((circle_x, y), 0.2, facecolor=INK, edgecolor="none", zorder=5))
    ax.text(circle_x, y, str(number), ha="center", va="center", color=PAPER,
             fontsize=10.5, fontweight="bold", zorder=6)
    ax.text(circle_x + 0.36, y, title, ha="left", va="center", color=INK,
             fontsize=12.5, fontweight="bold", zorder=6)
    if caption:
        ax.text(x, y_base + CAPTION_Y_OFFSET, caption, ha="center", va="top", color=MUTED,
                 fontsize=9.2, style="italic", zorder=6, linespacing=1.45)


def draw_document(ax, x, y, w=0.85, h=1.05, color=INPUT_C, lines=4, dog_ear=0.17):
    """A simple page-with-folded-corner icon, with a few text-line strokes."""
    body = Polygon([
        (x - w / 2, y - h / 2), (x + w / 2 - dog_ear, y - h / 2),
        (x + w / 2, y - h / 2 + dog_ear), (x + w / 2, y + h / 2),
        (x - w / 2, y + h / 2),
    ], closed=True, facecolor=PAPER, edgecolor=color, linewidth=1.7, zorder=3)
    ear = Polygon([
        (x + w / 2 - dog_ear, y - h / 2), (x + w / 2, y - h / 2 + dog_ear),
        (x + w / 2 - dog_ear, y - h / 2 + dog_ear),
    ], closed=True, facecolor=color, edgecolor="none", alpha=0.5, zorder=3)
    ax.add_patch(body)
    ax.add_patch(ear)
    for i in range(lines):
        ly = y + h / 2 - 0.26 - i * (h - 0.45) / max(lines - 1, 1)
        ax.plot([x - w / 2 + 0.14, x + w / 2 - 0.28 - 0.1 * (i % 2)], [ly, ly],
                 color=color, linewidth=1.3, alpha=0.55, zorder=4, solid_capstyle="round")


def draw_spreadsheet(ax, x, y, w=0.95, h=0.8, color=INPUT_C):
    """A minimal ruled grid icon representing tabular input data."""
    ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, facecolor=PAPER, edgecolor=color,
                            linewidth=1.7, zorder=2))
    for i in range(1, 3):
        ax.plot([x - w / 2, x + w / 2], [y - h / 2 + i * h / 3] * 2, color=color,
                 linewidth=1.0, alpha=0.6, zorder=2.5)
    for i in range(1, 4):
        ax.plot([x - w / 2 + i * w / 4] * 2, [y - h / 2, y + h / 2], color=color,
                 linewidth=1.0, alpha=0.6, zorder=2.5)
    ax.add_patch(Rectangle((x - w / 2, y - h / 2 + 2 * h / 3), w / 4, h / 3,
                            facecolor=color, alpha=0.3, edgecolor="none", zorder=2.6))


def draw_spark(ax, x, y, r=0.11, color=IDEATE_C, alpha=1.0, rays=True):
    """One idea: a filled dot, optionally with short radiating rays (a "spark"/idea glyph)."""
    ax.add_patch(Circle((x, y), r, facecolor=color, edgecolor="none", alpha=alpha, zorder=4))
    if rays:
        for ang in range(0, 360, 90):
            rad = math.radians(ang + 45)
            x0, y0 = x + math.cos(rad) * r * 1.6, y + math.sin(rad) * r * 1.6
            x1, y1 = x + math.cos(rad) * r * 2.7, y + math.sin(rad) * r * 2.7
            ax.plot([x0, x1], [y0, y1], color=color, linewidth=1.2, alpha=alpha * 0.75, zorder=4)


def draw_magnifier_check(ax, x, y, r=0.22, color=JUDGE_C):
    """A magnifying glass with a small checkmark inside - "each idea is examined and scored"."""
    ax.add_patch(Circle((x, y), r, facecolor=PAPER, edgecolor=color, linewidth=2.0, zorder=6))
    handle_dx, handle_dy = r * 0.75, -r * 0.75
    ax.plot([x + handle_dx * 0.95, x + handle_dx * 1.7], [y + handle_dy * 0.95, y + handle_dy * 1.7],
             color=color, linewidth=2.6, solid_capstyle="round", zorder=6)
    ax.plot([x - r * 0.4, x - r * 0.05, x + r * 0.45], [y - r * 0.05, y - r * 0.35, y + r * 0.35],
             color=color, linewidth=1.8, solid_capstyle="round", solid_joinstyle="round", zorder=6)


def draw_gear_shield(ax, x, y, r=0.42, color=REALISE_C):
    """A gear inside a shield outline: "built as real code, run in an isolated sandbox"."""
    n_teeth = 8
    outer = []
    for i in range(n_teeth * 2):
        ang = math.radians(i * 360 / (n_teeth * 2))
        rad = r * 0.6 if i % 2 == 0 else r * 0.76
        outer.append((x + math.cos(ang) * rad, y + math.sin(ang) * rad))
    shield = Polygon([
        (x - r, y + r * 0.55), (x, y + r), (x + r, y + r * 0.55),
        (x + r, y - r * 0.35), (x, y - r * 1.05), (x - r, y - r * 0.35),
    ], closed=True, facecolor="#FBEEE6", edgecolor=color, linewidth=1.8, zorder=3)
    ax.add_patch(shield)
    ax.add_patch(Polygon(outer, closed=True, facecolor=color, edgecolor="none",
                          alpha=0.9, zorder=4))
    ax.add_patch(Circle((x, y), r * 0.28, facecolor="#FBEEE6", edgecolor=color,
                         linewidth=1.4, zorder=5))


def draw_gallery(ax, x, y, w=1.5, h=4.0, color=INK, tiles=None):
    """The output document: a page whose body is a stack of colour-coded outcome tiles.

    `tiles` is a list of (colour, fraction_of_width, tile_y_centre) - one per realised outcome,
    each aligned so its stage-4 lane runs straight into its own tile rather than converging.
    """
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                 boxstyle="round,pad=0,rounding_size=0.06",
                                 facecolor=PAPER, edgecolor=color, linewidth=1.7, zorder=3))
    ax.plot([x - w / 2 + 0.12, x + w / 2 - 0.12], [y + h / 2 - 0.15] * 2,
             color=color, linewidth=2.0, zorder=4, solid_capstyle="round")
    for c, frac, ty in (tiles or []):
        bar_h = 0.28
        ax.add_patch(Rectangle((x - w / 2 + 0.14, ty - bar_h / 2),
                                (w - 0.28) * frac, bar_h,
                                facecolor=c, edgecolor="none", alpha=0.9, zorder=4))


def arrow(ax, xy_from, xy_to, color=MUTED, lw=1.6, connectionstyle="arc3,rad=0.0", alpha=1.0):
    ax.add_patch(FancyArrowPatch(xy_from, xy_to, arrowstyle="-|>", color=color,
                                  linewidth=lw, mutation_scale=12, zorder=1, alpha=alpha,
                                  connectionstyle=connectionstyle, shrinkA=2, shrinkB=2))


def main():
    fig, ax = plt.subplots(figsize=(19, 9), dpi=200)
    ax.set_xlim(0, 19)
    ax.set_ylim(0, 9)
    ax.axis("off")
    fig.patch.set_facecolor(PAPER)
    ax.set_facecolor(PAPER)

    baseline = 5.6

    # === Stage 1: input =====================================================================
    input_x = 1.5
    draw_document(ax, input_x - 0.15, baseline + 0.5)
    draw_spreadsheet(ax, input_x + 0.2, baseline - 0.5)
    stage_label(ax, input_x, baseline, 1, "Your inputs",
                "a short report describing the\nquestion, plus your dataset")
    arrow(ax, (input_x + 0.85, baseline), (3.6, baseline), color=INK, lw=1.8)

    # === Stage 2: fan-out (ideation) ========================================================
    fan_source = (3.75, baseline)
    n_ideas = 9
    idea_x = 4.7
    idea_ys = np.linspace(baseline - 2.0, baseline + 2.0, n_ideas)
    rng = np.random.default_rng(7)  # fixed seed - deterministic figure, not a data plot
    for iy in idea_ys:
        jitter_x = idea_x + rng.uniform(-0.1, 0.1)
        ax.plot([fan_source[0], jitter_x], [fan_source[1], iy], color=IDEATE_C,
                 linewidth=0.9, alpha=0.3, zorder=1)
        draw_spark(ax, jitter_x, iy, r=0.115)
    stage_label(ax, idea_x, baseline, 2, "Many independent ideas",
                "each one proposed on its own -\ne.g. 24 hypotheses per run")

    # === Stage 3: judge, then narrow (selection) ============================================
    neck_x = 8.7
    for iy in idea_ys:
        ax.plot([idea_x + 0.1, neck_x - 0.35], [iy, baseline], color=MUTED, linewidth=0.7,
                 alpha=0.35, zorder=0.5)
    # The magnifier sits on the bottleneck itself - scoring is what causes the narrowing.
    draw_magnifier_check(ax, neck_x, baseline)
    shortlist_y = baseline - 3.4
    arrow(ax, (neck_x, baseline - 0.28), (neck_x - 0.15, shortlist_y + 0.35), color=MUTED,
          lw=1.3, connectionstyle="arc3,rad=-0.25", alpha=0.7)
    for i in range(6):
        cx = neck_x - 0.55 + (i % 3) * 0.28
        cy = shortlist_y - (i // 3) * 0.28
        draw_spark(ax, cx, cy, r=0.075, color=MUTED, alpha=0.65, rays=False)
    ax.text(neck_x - 0.35, shortlist_y - 0.75, "kept as a shortlist -\njudged, never run as code",
             ha="center", va="top", color=MUTED, fontsize=8.6, style="italic", linespacing=1.4)
    stage_label(ax, neck_x, baseline, 3, "Scored, then narrowed",
                "how surprising is it, and how well\ndoes the data actually support it?")

    # === Stage 4: realise (build + sandbox-test) ============================================
    # Four parallel lanes - one per surviving idea - NOT a shared build step: each idea runs its
    # own orchestrator, workers, compile loop and Docker container independently (asyncio.gather),
    # so plurality survives all the way to the gallery instead of converging into a single script.
    lane_start_x = 10.4
    gear_x = 12.6
    gallery_x = 16.2
    gallery_w = 1.5
    lane_ys = [baseline - 2.1, baseline - 0.7, baseline + 0.7, baseline + 2.1]
    lane_colours = [NOT_REALISABLE_C, INCONCLUSIVE_C, DISCONFIRMED_C, CONFIRMED_C]  # bottom -> top
    for i, ky in enumerate(lane_ys):
        ax.plot([neck_x + 0.35, lane_start_x - 0.2], [baseline, ky], color=IDEATE_C,
                 linewidth=1.6, alpha=0.85, zorder=1.2, solid_capstyle="round")
        draw_spark(ax, lane_start_x, ky, r=0.1)
        ax.plot([lane_start_x + 0.2, gear_x - 0.42], [ky, ky], color=IDEATE_C,
                 linewidth=1.4, alpha=0.85, zorder=1.2, solid_capstyle="round")
        draw_gear_shield(ax, gear_x, ky, r=0.26)
        ax.plot([gear_x + 0.42, gallery_x - gallery_w / 2 + 0.14], [ky, ky], color=lane_colours[i],
                 linewidth=1.5, alpha=0.9, zorder=1.5, solid_capstyle="round")
    stage_label(ax, gear_x, baseline, 4, "Built and safety-tested",
                "turned into real code, run inside\nan isolated sandbox on your data")

    # === Stage 5: gallery ====================================================================
    gallery_tiles = [
        (CONFIRMED_C, 0.95, lane_ys[3]),
        (DISCONFIRMED_C, 0.85, lane_ys[2]),
        (INCONCLUSIVE_C, 0.6, lane_ys[1]),
        (NOT_REALISABLE_C, 0.7, lane_ys[0]),
    ]
    draw_gallery(ax, gallery_x, baseline, w=gallery_w, h=4.4, tiles=gallery_tiles)
    stage_label(ax, gallery_x, baseline, 5, "A skimmable report",
                "confirmed findings, useful non-\nfindings, side by side")

    legend_items = [
        (CONFIRMED_C, "confirmed"),
        (DISCONFIRMED_C, "checked, not supported"),
        (INCONCLUSIVE_C, "inconclusive"),
        (NOT_REALISABLE_C, "couldn't be built"),
    ]
    lx, ly = gallery_x - 0.55, baseline - 3.4
    for i, (c, label) in enumerate(legend_items):
        ax.add_patch(Rectangle((lx, ly - i * 0.4), 0.22, 0.16, facecolor=c, edgecolor="none"))
        ax.text(lx + 0.32, ly - i * 0.4 + 0.08, label, ha="left", va="center",
                 color=MUTED, fontsize=9)

    ax.set_aspect("equal", adjustable="box")
    fig.savefig("assets/pipeline_diagram.svg", format="svg", facecolor=PAPER,
                bbox_inches="tight", pad_inches=0.15)
    fig.savefig("assets/pipeline_diagram.png", format="png", facecolor=PAPER, dpi=200,
                bbox_inches="tight", pad_inches=0.15)
    print("Wrote assets/pipeline_diagram.svg and .png")


if __name__ == "__main__":
    main()
