import os
import logging
from typing import Optional
import pandas as pd
from scripts.smc.types import SetupSignal

logger = logging.getLogger(__name__)

try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive headless backend
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
except ImportError:
    plt = None
    patches = None


def generate_setup_chart(
    candles: pd.DataFrame,
    signal: SetupSignal,
    output_path: str = "data/latest_setup.png"
) -> Optional[str]:
    """
    Generates a dark-theme technical chart snapshot highlighting:
    - Candlestick bars
    - Sweep price level & wick
    - MSS swing level
    - FVG zone box
    - Entry, SL, and TP target lines
    Returns the output image path if successful, or None if matplotlib is unavailable.
    """
    if plt is None:
        logger.info("matplotlib not installed; skipping chart snapshot generation.")
        return None

    try:
        df = candles.tail(30).reset_index(drop=True)
        fig, ax = plt.subplots(figsize=(10, 6), facecolor="#121212")
        ax.set_facecolor("#181818")

        for i, row in df.iterrows():
            o, h, l, c = row["open"], row["high"], row["low"], row["close"]
            color = "#00e676" if c >= o else "#ff1744"
            # Wick
            ax.plot([i, i], [l, h], color=color, linewidth=1.2)
            # Body
            body_bottom = min(o, c)
            body_height = max(abs(c - o), 0.1)
            rect = patches.Rectangle(
                (i - 0.3, body_bottom),
                0.6,
                body_height,
                facecolor=color,
                edgecolor=color,
            )
            ax.add_patch(rect)

        # Plot levels
        ax.axhline(signal.entry_price, color="#00e5ff", linestyle="--", label=f"Entry: {signal.entry_price:.2f}")
        ax.axhline(signal.sl_price, color="#ff5252", linestyle="-.", label=f"SL: {signal.sl_price:.2f}")
        ax.axhline(signal.tp_price, color="#69f0ae", linestyle="-.", label=f"TP: {signal.tp_price:.2f}")

        # FVG zone box
        fvg_box = patches.Rectangle(
            (len(df) - 10, min(signal.fvg_low, signal.fvg_high)),
            10,
            abs(signal.fvg_high - signal.fvg_low),
            facecolor="#ffd600",
            alpha=0.18,
            label="FVG Zone"
        )
        ax.add_patch(fvg_box)

        ax.set_title(
            f"XAUUSD SMC Setup — {signal.direction.value} @ {signal.entry_price:.2f}",
            color="#ffffff",
            fontsize=13,
            pad=12
        )
        ax.tick_params(colors="#aaaaaa")
        for spine in ax.spines.values():
            spine.set_color("#333333")

        ax.legend(facecolor="#222222", edgecolor="#444444", labelcolor="#ffffff", loc="upper left")
        fig.tight_layout()
        if os.path.dirname(output_path):
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
        fig.savefig(output_path, dpi=120, facecolor=fig.get_facecolor(), edgecolor="none")
        plt.close(fig)

        return output_path
    except Exception as exc:
        logger.error("Failed to generate setup chart: %s", exc)
        return None
