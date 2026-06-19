"""Figure S: SR selection flow + gold PMID extraction workflow."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

plt.rcParams['font.family'] = 'DejaVu Sans'

fig, axes = plt.subplots(1, 2, figsize=(18, 20))
fig.patch.set_facecolor('white')


def box(ax, x, y, w, h, text, fc='white', ec='#333333', lw=1.2, fs=9.5, bold=False):
    rect = FancyBboxPatch((x - w/2, y - h/2), w, h,
                           boxstyle='round,pad=0.06',
                           facecolor=fc, edgecolor=ec, linewidth=lw, zorder=3)
    ax.add_patch(rect)
    ax.text(x, y, text, ha='center', va='center', fontsize=fs,
            fontweight='bold' if bold else 'normal',
            multialignment='center', zorder=4)


def arr(ax, x, y_from, y_to, color='#333333'):
    ax.annotate('', xy=(x, y_to + 0.03), xytext=(x, y_from - 0.03),
                arrowprops=dict(arrowstyle='->', color=color, lw=1.5), zorder=5)


def side_excl(ax, cx, cy, w, lines, fs=8.4):
    """Draw exclusion box; height auto-sized to text."""
    h = len(lines) * 0.34 + 0.20
    rect = FancyBboxPatch((cx - w/2, cy - h/2), w, h,
                           boxstyle='round,pad=0.07',
                           facecolor='#FADBD8', edgecolor='#C0392B',
                           linewidth=1.1, zorder=3)
    ax.add_patch(rect)
    ax.text(cx, cy, '\n'.join(lines), ha='center', va='center',
            fontsize=fs, color='#7B241C', multialignment='left', zorder=4)
    return h


def h_arrow(ax, x_start, x_end, y, color='#C0392B'):
    ax.annotate('', xy=(x_end - 0.05, y), xytext=(x_start + 0.05, y),
                arrowprops=dict(arrowstyle='->', color=color, lw=1.2), zorder=5)


# ════════════════════════════════════════════════════════════════════════
# PANEL A — SR Selection Flow
# ════════════════════════════════════════════════════════════════════════
ax = axes[0]
ax.set_xlim(0, 13.5)
ax.set_ylim(0, 21)
ax.axis('off')
ax.text(5.0, 20.5, 'A   SR Selection Flow',
        ha='center', va='center', fontsize=12, fontweight='bold', color='#1A5276')

CX = 4.2    # centre-x of main flow column
BW = 6.0    # box width
EXCL_CX = 10.5  # centre-x of exclusion boxes
EXCL_W = 4.5

# ── Box 1: PubMed search + eligibility assessment (merged) ──────────────
Y1 = 18.5
H1 = 1.5
box(ax, CX, Y1, BW, H1,
    'PubMed search for SRs / meta-analyses\npublished after August 2025  (five medical domains)\n'
    'Title / abstract screening and full-text eligibility assessment\n'
    '(n = 617 SRs identified and assessed)',
    fc='#EBF5FB', ec='#2E86C1', lw=1.3, fs=9.2)

# Exclusion box 1 (right of Box 1) — 21+88+10+420 = 539 excluded
excl1_lines = ['Excluded at eligibility screening  (n = 539):',
               '  Not in target domain  (n = 21)',
               '  No explicit I/E criteria  (n = 88)',
               '  No explicit PubMed query  (n = 10)',
               '  Full text not accessible  (n = 420)']
excl1_h = side_excl(ax, EXCL_CX, Y1 + 0.3, EXCL_W, excl1_lines, fs=8.2)
h_arrow(ax, CX + BW/2, EXCL_CX - EXCL_W/2, Y1 + 0.3)

# ── Box 2: Gold PMID extraction ─────────────────────────────────────────
Y2 = 16.0
H2 = 1.1
arr(ax, CX, Y1 - H1/2, Y2 + H2/2)
box(ax, CX, Y2, BW, H2,
    'Gold PMID extraction & verification\n(5-step workflow; see Panel B)',
    fc='#EBF5FB', ec='#2E86C1', lw=1.3, fs=9.2)

# ── Box 3: Adopted ──────────────────────────────────────────────────────
Y3 = 14.2
H3 = 1.0
arr(ax, CX, Y2 - H2/2, Y3 + H3/2)
box(ax, CX, Y3, BW, H3,
    'Adopted to benchmark dataset\n(n = 38;  strict PMID verification)',
    fc='#D5F5E3', ec='#1E8449', lw=1.3, fs=9.2)

# Exclusion box 2 (right of Box 3)
excl2_lines = ['Excluded post-adoption (n = 3)',
               '  Re-evaluation: gold PMIDs failed',
               '  strict QC  (CV: 1, RA: 1, ONC: 1)']
side_excl(ax, EXCL_CX, Y3, EXCL_W, excl2_lines)
h_arrow(ax, CX + BW/2, EXCL_CX - EXCL_W/2, Y3)

# ── Box 4: Final dataset ────────────────────────────────────────────────
Y4 = 12.4
H4 = 0.9
arr(ax, CX, Y3 - H3/2, Y4 + H4/2)
box(ax, CX, Y4, BW, H4,
    'Final benchmark dataset  (n = 35)',
    fc='#D5F5E3', ec='#1E8449', lw=2.0, fs=10.0, bold=True)

# ── Fork into Training / Test ────────────────────────────────────────────
fork_top = Y4 - H4/2 - 0.15
fork_bot = fork_top - 0.55
ax.plot([CX, CX], [fork_top, fork_bot], color='#333', lw=1.5, zorder=5)
ax.plot([1.8, 6.6], [fork_bot, fork_bot], color='#333', lw=1.5, zorder=5)

TRY = fork_bot - 0.95
TSY = fork_bot - 1.10

ax.annotate('', xy=(1.8, TRY + 0.5), xytext=(1.8, fork_bot),
            arrowprops=dict(arrowstyle='->', color='#333', lw=1.4), zorder=5)
ax.annotate('', xy=(6.6, TSY + 0.65), xytext=(6.6, fork_bot),
            arrowprops=dict(arrowstyle='->', color='#333', lw=1.4), zorder=5)

box(ax, 1.8, TRY, 3.2, 1.0,
    'Training set  (n = 11)\nCV: 3  |  PSY: 4  |  INF: 4',
    fc='#EAF4FF', ec='#2E6FA3', lw=1.5, fs=9.5)

box(ax, 6.6, TSY, 3.2, 1.3,
    'Test set  (n = 24)\nCV: 4  |  PSY: 3  |  INF: 3\nRA: 7  |  ONC: 7',
    fc='#FEF9E7', ec='#D4AC0D', lw=1.5, fs=9.5)


# ════════════════════════════════════════════════════════════════════════
# PANEL B — Gold PMID Extraction Workflow (plain language, no script names)
# ════════════════════════════════════════════════════════════════════════
ax2 = axes[1]
ax2.set_xlim(-0.5, 10.5)
ax2.set_ylim(0, 21)
ax2.axis('off')
ax2.text(5.0, 20.5, 'B   Gold PMID Extraction Workflow (per SR)',
         ha='center', va='center', fontsize=12, fontweight='bold', color='#4A235A')

RX = 5.0
RW = 9.2
STEPS = [
    (19.1, 1.05,
     'Step 1  Manual identification of included-study reference numbers\n'
     'Open published SR and locate included studies in:\n'
     'Table 1 / study characteristics table, Results text, or PRISMA diagram'),
    (17.3, 1.05,
     'Step 2  (Optional) PDF text sanity check\n'
     'Verify that text extraction is accurate before parsing\n'
     'Repair broken PDFs using PMC HTML or supplementary files if needed'),
    (15.5, 1.05,
     'Step 3  Structured extraction of reference fields\n'
     'Parse each included-study reference into: Authors, Title, Journal,\n'
     'Year / Volume / Issue, DOI, and PMID'),
    (13.7, 1.05,
     'Step 4  Automated PMID lookup via PubMed API\n'
     'Search priority: DOI  ->  Title + First Author + Year  ->  raw citation\n'
     'Each matched PMID is recorded against the corresponding reference'),
    (11.9, 1.05,
     'Step 5  Title-level PMID verification\n'
     'Fetch title from PubMed using the assigned PMID;\n'
     'title similarity >= 0.9  ->  OK  |  mismatch  ->  REVIEW or NG'),
]

for y, h, txt in STEPS:
    box(ax2, RX, y, RW, h, txt, fc='#F5EEF8', ec='#7D3C98', lw=1.2, fs=9.0)

for i in range(len(STEPS) - 1):
    y_top, h_top, _ = STEPS[i]
    y_bot, h_bot, _ = STEPS[i + 1]
    arr(ax2, RX, y_top - h_top / 2, y_bot + h_bot / 2, '#7D3C98')

# QC
qc_y = 10.4
box(ax2, RX, qc_y, RW, 0.85,
    'Quality check: all REVIEW / NG rows resolved manually\n'
    'or excluded from the gold standard (target: 100% verified)',
    fc='#D5F5E3', ec='#1E8449', lw=1.3, fs=9.0)
arr(ax2, RX, STEPS[-1][0] - STEPS[-1][1] / 2, qc_y + 0.425, '#1E8449')

# Output
out_y = 9.1
box(ax2, RX, out_y, RW, 0.85,
    'Output: verified gold PMID list\n'
    'Used as ground truth for recall evaluation',
    fc='#EAF4FF', ec='#2E6FA3', lw=1.8, fs=9.5, bold=True)
arr(ax2, RX, qc_y - 0.425, out_y + 0.425, '#2E6FA3')

ax2.text(RX, 7.8,
         'Studies available only as dissertations without a journal publication,\n'
         'published in non-English languages without a PubMed ID, or lacking\n'
         'a PubMed abstract were excluded from the gold standard.',
         ha='center', va='center', fontsize=8.5, color='#555',
         style='italic', multialignment='center')

plt.tight_layout(pad=2.0)
from pathlib import Path
_SCRIPT_DIR = Path(__file__).resolve().parent
_OUT_DIR = _SCRIPT_DIR.parent / "figures"
_OUT_DIR.mkdir(parents=True, exist_ok=True)
outpath = _OUT_DIR / "figureS_sr_selection_flow.png"
fig.savefig(outpath, dpi=200, bbox_inches='tight', facecolor='white')
print("Saved:", outpath)
