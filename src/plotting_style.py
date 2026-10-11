"""Reusable minimalist, light-mode styling for static research figures."""
from contextlib import contextmanager
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BLUE = '#527D9D'
ORANGE = '#C58B57'
GRAY = '#88939D'
STYLE = {
    'figure.facecolor': 'white', 'axes.facecolor': 'white',
    'savefig.facecolor': 'white', 'font.family': 'DejaVu Sans',
    'font.size': 10, 'axes.titlesize': 12, 'axes.labelsize': 10,
    'xtick.labelsize': 9, 'ytick.labelsize': 9, 'legend.fontsize': 9,
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.edgecolor': '#BCC3C9', 'axes.linewidth': 0.6,
    'grid.color': '#E9ECEF', 'grid.linewidth': 0.5,
    'lines.linewidth': 1.5, 'legend.frameon': False,
    'figure.figsize': (7.2, 4.8), 'savefig.dpi': 300,
}

@contextmanager
def light_style():
    with plt.rc_context(STYLE):
        yield


def save_figure(fig, path, caption=None):
    """Use consistent dimensions; reserve space for a modest methodological caption."""
    if caption:
        fig.text(0.5, 0.015, caption, ha='center', va='bottom', fontsize=8, color='#616970')
    fig.tight_layout(rect=(0, 0.055 if caption else 0, 1, 1))
    fig.savefig(path, dpi=300, facecolor='white', metadata={'Software': 'Steam Phase 7A'})
    plt.close(fig)
