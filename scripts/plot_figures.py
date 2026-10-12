#!/usr/bin/env python3
"""Render the retained prefix-defect control; no schedule experiment is run."""
from pathlib import Path
import argparse
import csv
import os
import shutil
import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt, font_manager
from matplotlib.ticker import NullLocator

ROOT = Path(__file__).resolve().parents[1]


def configure_fonts():
    directory = Path(os.environ.get("FIGURE_FONT_DIR", os.environ.get("WINDIR", "")))
    if not os.environ.get("FIGURE_FONT_DIR"):
        directory /= "Fonts"
    files = [directory / "times.ttf", directory / "timesi.ttf"]
    if all(path.is_file() for path in files):
        for path in files:
            font_manager.fontManager.addfont(str(path))
        family = font_manager.FontProperties(fname=str(files[0])).get_name()
    else:
        family = "STIXGeneral"  # Bundled Times-compatible serif fallback.
    plt.rcParams.update({"font.family": family, "font.size": 7.97,
                         "mathtext.fontset": "custom", "mathtext.rm": family,
                         "mathtext.it": family + ":style=italic",
                         "mathtext.bf": family, "mathtext.fallback": None,
                         "text.usetex": False, "pdf.fonttype": 42,
                         "ps.fonttype": 42, "pdf.use14corefonts": False,
                         "axes.linewidth": .4, "xtick.major.width": .4,
                         "ytick.major.width": .4, "xtick.major.size": 2.5,
                         "ytick.major.size": 2.5})
    print("Font:", family)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "figures")
    parser.add_argument("--paper-dir", type=Path, default=ROOT.parent / "paper" / "figures")
    args = parser.parse_args()
    with (ROOT / "results/prefix-defect.csv").open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    x, y = [int(r["prefix"]) for r in rows], [int(r["defect"]) for r in rows]
    assert x == [0, 1, 2, 3, 4] and y == [0, 1, 1, 1, 2]
    configure_fonts()
    fig = plt.figure(figsize=(236.788 / 72, 127.4971 / 72))
    ax = fig.add_axes([29.0 / 236.788, 27.8 / 127.4971,
                       205.8 / 236.788, 94.05 / 127.4971])
    ax.step(x, y, where="post", color="black", linewidth=.8)
    ax.plot(x, y, linestyle="none", marker="o", color="black", markersize=3.4,
            clip_on=False)
    ax.set(xlim=(0, 4), ylim=(0, 2.25), xlabel=r"Prefix length $t$", ylabel=r"Defect $D(t)$")
    ax.set_xticks(x)
    ax.set_yticks([0, 1, 2])
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(direction="out", pad=3)
    ax.xaxis.set_minor_locator(NullLocator())
    ax.yaxis.set_minor_locator(NullLocator())
    ax.plot(4, 0, marker=">", markersize=3, color="black", clip_on=False)
    ax.plot(0, 2.25, marker="^", markersize=3, color="black", clip_on=False)
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "prefix-defect.pdf"
    fig.savefig(path, metadata={"Creator": None, "Producer": None,
                                "CreationDate": None, "ModDate": None})
    plt.close(fig)
    if args.paper_dir.is_dir():
        shutil.copyfile(path, args.paper_dir / path.name)
    print("Rendered prefix-defect: 5 unchanged integer points, post-step semantics")


if __name__ == "__main__":
    main()
