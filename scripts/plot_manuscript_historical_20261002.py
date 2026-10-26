"""Scientific figure from the authoritative, corrected historical statistics.

No inference and no changed scores. Run only outside the live measurement window.
"""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os

ROOT = Path(__file__).resolve().parents[1]
MPL_CACHE = ROOT / ".runtime/matplotlib_manuscript_20261002"
MPL_CACHE.mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(MPL_CACHE)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SOURCE = ROOT / "results/analysis_input_reconciled_20261002_052358Z_804ced2b/analysis_20261002_052438Z_2c0beea8/statistics_reporting_corrected.json"


def main() -> None:
    stats = json.loads(SOURCE.read_text(encoding="utf-8"))
    effect = stats["paired"]["hybrid_minus_tool_cloud"]["quality_a_minus_b"]
    estimate = effect["estimate"] * 100
    lo, hi = [value*100 for value in effect["ci95"]]
    margin = -5.0  # frozen protocol's research choice; not an agronomic standard
    dest = ROOT / "manuscript/figures"
    dest.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "pdf.fonttype": 42, "ps.fonttype": 42})
    fig, ax = plt.subplots(figsize=(6.8, 2.6), constrained_layout=True)
    ax.axvspan(-25, margin, color="#F8EEE8", zorder=0)
    ax.axvline(margin, color="#AD623E", linewidth=1.5, linestyle="--", label="Frozen NI margin: -5 pp")
    ax.axvline(0, color="#5E6F7B", linewidth=1.1, linestyle=":", label="No quality difference")
    ax.errorbar(estimate, 0, xerr=[[estimate-lo], [hi-estimate]], fmt="o", color="#234B6B",
                ecolor="#234B6B", linewidth=2.5, markersize=8, capsize=7)
    ax.text(estimate, 0.23, f"Estimate {estimate:+.2f} pp", ha="center", va="bottom", color="#234B6B", weight="bold")
    ax.text(lo, -0.23, f"{lo:.2f}", ha="center", va="top")
    ax.text(hi, -0.23, f"{hi:+.2f}", ha="center", va="top")
    ax.set(xlim=(-25, 15), ylim=(-0.55, 0.62), yticks=[],
           xlabel="Quality difference: hybrid minus tools + cloud (percentage points)")
    ax.set_title("Quality non-inferiority was not demonstrated", loc="left", fontsize=12, weight="bold", pad=10)
    ax.spines[["top", "left", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=.12)
    ax.legend(loc="upper right", fontsize=8.2, frameon=False)
    base = dest / "historical_noninferiority_20261002"
    files = []
    for suffix in ["png", "svg", "pdf"]:
        target = base.with_suffix("."+suffix)
        fig.savefig(target, dpi=220 if suffix=="png" else None)
        files.append({"path": str(target.relative_to(ROOT)), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    plt.close(fig)
    metadata = {"created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "source": str(SOURCE.relative_to(ROOT)), "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                "contrast": "hybrid minus tool_cloud", "estimate_pp": estimate, "ci95_pp": [lo, hi],
                "research_noninferiority_margin_pp": margin, "quality_criterion_met": lo >= margin,
                "paired_n": effect["n"], "groups": effect["n_groups"], "bootstrap_repeats": effect["repeats"],
                "seed": effect["seed"], "human_review": False,
                "interpretation": "Lower CI bound below -5 pp; failure to prove non-inferiority is not proof of statistically significant inferiority", "files": files}
    (dest/"historical_noninferiority_20261002_manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"estimate_pp": estimate, "ci95_pp": [lo,hi], "files":len(files)}))


if __name__ == "__main__":
    main()
