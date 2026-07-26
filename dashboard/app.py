"""EcoLoop Building Energy Management dashboard.

Frontend/presentation layer only. Reads CSV telemetry produced by the
EnergyPlus runtime loop (src/phase3a_llm_loop.py) and the baseline run
(src/phase3d_baseline.py) — no simulation or LLM logic lives here.
"""

import datetime as dt
import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from pandas.errors import EmptyDataError


def _compact_html(html: str) -> str:
    """Collapse whitespace between tags.

    st.markdown runs raw HTML through a CommonMark parser first. Lines
    indented >=4 spaces (as our triple-quoted templates naturally are) get
    read as indented code blocks once a blank-ish line breaks the HTML
    block, so multi-card rows after the first render as literal text.
    Flattening to one line sidesteps that entirely.
    """
    return re.sub(r">\s+<", "><", html.strip())

BASE_DIR = Path(__file__).resolve().parent.parent
AI_LOG_PATH = BASE_DIR / "out" / "ai_loop" / "ai_loop_log.csv"
BASELINE_LOG_PATH = BASE_DIR / "out" / "baseline" / "baseline_log.csv"
GUARDRAIL_LOG_PATH = BASE_DIR / "out" / "ai_loop" / "guardrail_events.csv"
FLOORPLAN_SVG_PATH = BASE_DIR / "assets" / "hvac-floor-plan.svg"

ZONES = ["SPACE1-1", "SPACE2-1", "SPACE3-1", "SPACE4-1", "SPACE5-1"]
ZONE_ROOM_NAMES = {
    "SPACE1-1": "Office 1",
    "SPACE2-1": "Office 2",
    "SPACE3-1": "Meeting Room",
    "SPACE4-1": "Lobby",
    "SPACE5-1": "Conference Room",
}
LIVE_STALE_SECONDS = 15  # CSV silent for longer than this reads as "idle"

# ---------------------------------------------------------------------------
# Colors — light, physical, engineered. No saturated/neon values.
# Background: off-white/limestone. Primary: charcoal + deep steel blue for
# text, headers and structure. Sage/terracotta are reserved strictly for
# status semantics (normal vs. attention) — never used decoratively.
#
# Borders and secondary/tertiary text below were tuned against measured
# WCAG contrast ratios (not eyeballed) — the first pass used a taupe border
# at 1.4:1 and a tertiary gray at 3.2:1 against the card surface, both of
# which read as "missing" rather than "subtle". These sit at ~2.3:1 (border)
# and ~4.3-7:1 (text) instead.
#
# The digital twin and header strip use a dark charcoal "ink" canvas rather
# than the page's light surface — real BMS/SCADA graphics screens are
# conventionally rendered on a dark canvas for equipment-schematic contrast
# even inside an otherwise light application shell.
# ---------------------------------------------------------------------------
COLOR_BG = "#EDE9E0"                     # pale limestone — never pure white
COLOR_PANEL = "#F8F6F1"                  # card surface, warm off-white
COLOR_PANEL_ALT = "#D8CEB5"              # inset/track surface (bars)
COLOR_BORDER = "rgba(43,46,51,0.40)"     # structural hairline border
COLOR_BORDER_STRONG = "rgba(43,46,51,0.62)"  # section rules, header divider
COLOR_TEXT_PRIMARY = "#2B2E33"           # structural charcoal
COLOR_TEXT_SECONDARY = "#4B4E48"         # muted charcoal
COLOR_TEXT_TERTIARY = "#6E6F63"          # muted stone gray
COLOR_STEEL = "#3E5266"                  # deep steel blue — structural accent
COLOR_SAGE = "#71835F"                   # muted sage green — status: normal
COLOR_TERRACOTTA = "#B5623F"             # muted terracotta — status: attention

COLOR_INK = "#20242B"                    # dark canvas: header strip + twin
COLOR_ON_INK = "#EDE9E0"                 # primary text/lines on the ink canvas
COLOR_ON_INK_DIM = "rgba(237,233,224,0.62)"
COLOR_ON_INK_FAINT = "rgba(237,233,224,0.20)"
COLOR_SAGE_ON_INK = "#93A67D"            # lightened sage, legible on COLOR_INK

FONT_UI = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif"
FONT_MONO = "Consolas, 'Cascadia Mono', 'Courier New', monospace"

# PMV comfort bands: (upper bound, label, badge/dot color — tuned for the
# light panel surface; reused at low opacity as the floorplan tint on the
# dark twin canvas)
COMFORT_BANDS = [
    (-0.2, "Cold", "#3E5266"),
    (-0.05, "Cool", "#5C7A8C"),
    (0.05, "Comfortable", "#71835F"),
    (0.2, "Warm", "#C0865B"),
    (float("inf"), "Hot", "#B5623F"),
]

ICON_BOLT = """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2 3 14h7l-1 8 10-12h-7l1-8Z"/></svg>"""
ICON_GAUGE = """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20a7 7 0 1 0-7-7"/><path d="M12 13 15.5 9"/><circle cx="12" cy="13" r="1"/></svg>"""
ICON_USERS = """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2"/><circle cx="10" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>"""
ICON_CPU = """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3"/></svg>"""
ICON_THERMO = """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4v10.5a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"/></svg>"""
ICON_SNOWFLAKE = """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M4.2 6l15.6 12M19.8 6 4.2 18"/></svg>"""


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data(ttl=2)
def load_csv(path: Path):
    if not path.exists():
        return None

    try:
        return pd.read_csv(path, encoding="latin-1")
    except EmptyDataError:
        return None

@st.cache_data
def load_svg_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Derived data helpers
# ---------------------------------------------------------------------------
def comfort_band(pmv: float) -> tuple[str, str]:
    """Return (label, badge_color) for a PMV value."""
    for upper, label, color in COMFORT_BANDS:
        if pmv <= upper:
            return label, color
    return COMFORT_BANDS[-1][1], COMFORT_BANDS[-1][2]


def build_zone_records(latest: pd.Series) -> list[dict]:
    records = []
    for zone in ZONES:
        pmv = float(latest[f"{zone}_pmv"])
        label, color = comfort_band(pmv)
        records.append({
            "zone": zone,
            "room": ZONE_ROOM_NAMES[zone],
            "temp": float(latest[f"{zone}_temp_c"]),
            "pmv": pmv,
            "setpoint": float(latest[f"{zone}_setpoint_applied"]),
            "occupied": bool(float(latest[f"{zone}_occupancy"]) > 0),
            "comfort_label": label,
            "comfort_color": color,
        })
    return records


def select_priority_zone(zone_records: list[dict]) -> dict:
    """Occupied zones take priority; within that, largest comfort deviation wins."""
    return max(zone_records, key=lambda r: (r["occupied"], abs(r["pmv"])))


def find_guardrail_action(guardrail_df: pd.DataFrame | None, timestep, zone: str) -> str | None:
    if guardrail_df is None or guardrail_df.empty:
        return None
    match = guardrail_df[(guardrail_df["timestep"] == timestep) & (guardrail_df["zone"] == zone)]
    if match.empty:
        return None
    row = match.iloc[-1]
    return (
        f"Guardrail intervened ({row['reason'].replace('_', ' ')}) — proposed "
        f"{float(row['proposed_setpoint']):.1f}°C clamped to "
        f"{float(row['applied_setpoint']):.1f}°C."
    )


def build_decision_reason(zone_rec: dict):
    if zone_rec["occupied"]:
        return (
            f"{zone_rec['room']} is occupied with a PMV of "
            f"{zone_rec['pmv']:+.2f}. The controller evaluated occupant "
            f"comfort against HVAC energy consumption and selected a "
            f"{zone_rec['setpoint']:.1f}°C setpoint to maintain comfort "
            f"while minimizing unnecessary cooling."
        )

    return (
        f"{zone_rec['room']} is currently unoccupied. The controller "
        f"maintains an energy-efficient setpoint of "
        f"{zone_rec['setpoint']:.1f}°C while ensuring the zone remains "
        f"within acceptable thermal limits."
    )


def is_feed_live(path: Path) -> bool:
    if not path.exists():
        return False
    age = dt.datetime.now().timestamp() - path.stat().st_mtime
    return age <= LIVE_STALE_SECONDS


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------
def inject_theme():
    st.markdown(f"""
    <style>
    html, body, [class*="css"] {{
        font-family: {FONT_UI};
    }}
    .stApp {{
        background: {COLOR_BG};
    }}
    .block-container {{
        padding: 0 2.75rem 3rem 2.75rem;
        max-width: 1800px;
    }}
    #MainMenu, footer, header {{ visibility: hidden; }}

    /* ---------- Header: dark toolbar strip, full-bleed ---------- */
    .eco-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: {COLOR_INK};
        margin: 0 -2.75rem 26px -2.75rem;
        padding: 15px 2.75rem;
        border-bottom: 1px solid rgba(237,233,224,0.14);
    }}
    .eco-header-id {{
        font-family: {FONT_MONO};
        font-size: 15px;
        font-weight: 600;
        letter-spacing: 0.03em;
        color: {COLOR_ON_INK};
        margin: 0;
    }}
    .eco-header-sub {{
        font-size: 12px;
        color: {COLOR_ON_INK_DIM};
        margin: 3px 0 0 0;
    }}
    .eco-header-meta {{
        text-align: right;
        font-family: {FONT_MONO};
        font-size: 11.5px;
        color: {COLOR_ON_INK_DIM};
        line-height: 1.7;
    }}
    .live-dot {{
        display: inline-block;
        width: 7px;
        height: 7px;
        border-radius: 50%;
        margin-right: 6px;
        position: relative;
        top: -1px;
    }}
    .live-dot.on {{
        background: {COLOR_SAGE_ON_INK};
        box-shadow: 0 0 0 0 rgba(147,166,125,0.5);
        animation: pulse 2s infinite;
    }}
    .live-dot.off {{ background: {COLOR_ON_INK_DIM}; }}
    @keyframes pulse {{
        0% {{ box-shadow: 0 0 0 0 rgba(147,166,125,0.45); }}
        70% {{ box-shadow: 0 0 0 6px rgba(147,166,125,0); }}
        100% {{ box-shadow: 0 0 0 0 rgba(147,166,125,0); }}
    }}
    .live-label {{ font-weight: 600; letter-spacing: 0.04em; font-size: 11px; }}
    .live-label.on {{ color: {COLOR_SAGE_ON_INK}; }}
    .live-label.off {{ color: {COLOR_ON_INK_DIM}; }}

    /* ---------- Section titles: numbered, ruled like a drawing set ---------- */
    .eco-section-title {{
        display: flex;
        align-items: baseline;
        gap: 10px;
        padding-bottom: 7px;
        margin: 32px 0 14px 0;
        border-bottom: 1px solid {COLOR_BORDER_STRONG};
    }}
    .eco-section-title .sec-index {{
        font-family: {FONT_MONO};
        font-size: 11px;
        color: {COLOR_TEXT_TERTIARY};
    }}
    .eco-section-title .sec-text {{
        font-size: 12.5px;
        font-weight: 700;
        letter-spacing: 0.07em;
        text-transform: uppercase;
        color: {COLOR_TEXT_SECONDARY};
    }}

    /* ---------- KPI cards ---------- */
    .kpi-row {{ display: flex; gap: 14px; }}
    .kpi-card {{
        flex: 1;
        background: {COLOR_PANEL};
        border: 1px solid {COLOR_BORDER};
        border-radius: 3px;
        padding: 14px 16px;
    }}
    .kpi-label {{
        display: flex; align-items: center; gap: 6px;
        font-size: 11px;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: {COLOR_TEXT_TERTIARY};
    }}
    .kpi-label svg {{ opacity: 0.75; flex-shrink: 0; }}
    .kpi-value {{
        font-family: {FONT_MONO};
        font-size: 25px;
        font-weight: 600;
        color: {COLOR_TEXT_PRIMARY};
        margin-top: 8px;
    }}
    .kpi-sub {{ font-size: 11.5px; color: {COLOR_TEXT_SECONDARY}; margin-top: 3px; }}

    /* ---------- Generic panel ---------- */
    .eco-panel {{
        background: {COLOR_PANEL};
        border: 1px solid {COLOR_BORDER};
        border-radius: 3px;
        padding: 20px 22px;
    }}

    /* ---------- Comparison card ---------- */
    .cmp-row {{ margin-bottom: 16px; }}
    .cmp-row:last-child {{ margin-bottom: 0; }}
    .cmp-row-head {{
        display: flex; justify-content: space-between; align-items: baseline;
        font-size: 12.5px; color: {COLOR_TEXT_SECONDARY}; margin-bottom: 6px;
    }}
    .cmp-row-value {{ font-family: {FONT_MONO}; color: {COLOR_TEXT_PRIMARY}; font-size: 13px; }}
    .bar-track {{
        width: 100%; height: 10px; border-radius: 2px;
        background: {COLOR_PANEL_ALT}; border: 1px solid {COLOR_BORDER}; overflow: hidden;
    }}
    .bar-fill {{ height: 100%; }}
    .cmp-summary {{
        margin-top: 18px;
        padding-top: 16px;
        border-top: 1px solid {COLOR_BORDER};
        display: flex; align-items: baseline; gap: 10px;
    }}
    .cmp-summary-value {{ font-size: 28px; font-weight: 700; color: {COLOR_SAGE}; font-family: {FONT_MONO}; }}
    .cmp-summary-label {{ font-size: 12.5px; color: {COLOR_TEXT_SECONDARY}; }}

    /* ---------- Decision panel ---------- */
    .decision-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0 32px; }}
    .decision-row {{
        display: flex; justify-content: space-between; align-items: baseline;
        padding: 10px 0; border-bottom: 1px solid {COLOR_BORDER};
    }}
    .decision-row.full {{ grid-column: 1 / -1; }}
    .decision-label {{
        font-size: 11px; letter-spacing: 0.05em; text-transform: uppercase;
        color: {COLOR_TEXT_TERTIARY};
    }}
    .decision-value {{ font-size: 13px; color: {COLOR_TEXT_PRIMARY}; font-family: {FONT_MONO}; text-align: right; max-width: 62%; }}

    /* ---------- Legend ---------- */
    .legend-row {{ display: flex; gap: 22px; flex-wrap: wrap; margin: 10px 0 14px 2px; }}
    .legend-item {{ display: flex; align-items: center; gap: 7px; font-size: 12px; color: {COLOR_TEXT_SECONDARY}; }}
    .legend-dot {{ width: 9px; height: 9px; border-radius: 2px; display: inline-block; }}

    /* ---------- Telemetry cards ---------- */
    .tel-row {{ display: flex; gap: 12px; }}
    .tel-card {{
        flex: 1; background: {COLOR_PANEL}; border: 1px solid {COLOR_BORDER};
        border-radius: 3px; padding: 12px 14px;
    }}
    .tel-label {{ display: flex; align-items: center; gap: 6px; font-size: 10.5px; letter-spacing: 0.05em; text-transform: uppercase; color: {COLOR_TEXT_TERTIARY}; }}
    .tel-label svg {{ opacity: 0.75; flex-shrink: 0; }}
    .tel-value {{ font-size: 18px; font-weight: 600; color: {COLOR_TEXT_PRIMARY}; margin-top: 6px; font-family: {FONT_MONO}; }}
    .tel-value.dim {{ color: {COLOR_TEXT_TERTIARY}; font-weight: 400; }}

    /* ---------- Digital twin: dark canvas, matches the header strip ---------- */
    .twin-frame {{
        background: {COLOR_INK};
        border: 1px solid {COLOR_BORDER};
        border-radius: 3px;
        padding: 14px;
        display: flex;
        justify-content: center;
    }}

    div[data-testid="stCaptionContainer"] p {{ color: {COLOR_TEXT_TERTIARY}; }}
    </style>
    """, unsafe_allow_html=True)


def render_header(latest: pd.Series, live: bool):
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sim_time = f"Day {int(latest['day'])} · {int(latest['hour']):02d}:{int(latest['minute']) % 60:02d}"
    if live:
     live_class = "on"
     live_text = "LIVE"
    else:
     live_class = "off"
     live_text = "SIMULATION COMPLETE"
    st.markdown(_compact_html(f"""
    <div class="eco-header">
        <div>
            <p class="eco-header-id">ECOLOOP // BUILDING ENERGY MANAGEMENT</p>
            <p class="eco-header-sub">Runtime HVAC Control &mdash; EnergyPlus Runtime API + Local LLM</p>
        </div>
        <div class="eco-header-meta">
            <div>{now}</div>
            <div>Simulation time &mdash; {sim_time}</div>
            <div><span class="live-dot {live_class}"></span><span class="live-label {live_class}">{live_text}</span></div>
        </div>
    </div>
    """), unsafe_allow_html=True)


def render_section_title(index: int, text: str):
    st.markdown(_compact_html(f"""
    <div class="eco-section-title">
        <span class="sec-index">{index:02d}</span>
        <span class="sec-text">{text}</span>
    </div>
    """), unsafe_allow_html=True)


def kpi_card(icon: str, label: str, value: str, sub: str = "", accent: str = COLOR_STEEL) -> str:
    return _compact_html(f"""
    <div class="kpi-card" style="border-left: 3px solid {accent}">
        <div class="kpi-label">{icon}{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>
    """)


def render_kpi_row(
    latest,
    zone_records,
    live,
    saving_pct,
    energy_saved,
    cost_saved,
    co2_saved,
):
    avg_pmv = sum(r["pmv"] for r in zone_records) / len(zone_records)
    occupied = sum(1 for r in zone_records if r["occupied"])
    avg_label, avg_color = comfort_band(avg_pmv)

    cards = [
    kpi_card(
        ICON_BOLT,
        "Energy Saved",
        f"{saving_pct:.1f}%",
        f"{energy_saved:.1f} kWh saved",
        COLOR_SAGE,
    ),

    kpi_card(
        ICON_BOLT,
        "Cost Saved",
        f"${cost_saved:.2f}",
        "Estimated electricity savings",
        COLOR_SAGE,
    ),

    kpi_card(
        ICON_BOLT,
        "CO₂ Reduced",
        f"{co2_saved:.1f} kg",
        "Estimated emissions avoided",
        COLOR_SAGE,
    ),

    kpi_card(
    ICON_GAUGE,
    "Comfort Maintained",
    f"{comfort_pct:.1f}%",
    "Occupied PMV within target",
    COLOR_SAGE,
),
]
    st.markdown(_compact_html(f'<div class="kpi-row">{"".join(cards)}</div>'), unsafe_allow_html=True)


def render_comparison_card(baseline_kw: float, ai_kw: float):
    max_kw = max(baseline_kw, ai_kw, 0.01)
    baseline_pct = min(100, baseline_kw / max_kw * 100)
    ai_pct = min(100, ai_kw / max_kw * 100)
    savings_pct = ((baseline_kw - ai_kw) / baseline_kw * 100) if baseline_kw else 0.0
    direction = "↓" if savings_pct >= 0 else "↑"
    summary_color = COLOR_SAGE if savings_pct >= 0 else COLOR_TERRACOTTA

    st.markdown(_compact_html(f"""
    <div class="eco-panel">
        <div class="cmp-row">
            <div class="cmp-row-head"><span>Baseline</span><span class="cmp-row-value">{baseline_kw:.1f} kWh</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:{baseline_pct:.1f}%; background:{COLOR_TEXT_TERTIARY};"></div></div>
        </div>
        <div class="cmp-row">
            <div class="cmp-row-head"><span>AI Runtime</span><span class="cmp-row-value">{ai_kw:.1f} kWh</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:{ai_pct:.1f}%; background:{COLOR_STEEL};"></div></div>
        </div>
        <div class="cmp-summary">
            <span class="cmp-summary-value" style="color:{summary_color}">{direction} {abs(savings_pct):.1f}%</span>
            <span class="cmp-summary-label">Energy Saved ({baseline_kw - ai_kw:.1f} kWh)</span>
        </div>
    </div>
    """), unsafe_allow_html=True)


def render_decision_panel(zone_rec: dict, reason: str, action: str):
    st.markdown(_compact_html(f"""
    <div class="eco-panel">
        <div class="decision-grid">
            <div class="decision-row">
                <span class="decision-label">Priority Zone</span>
                <span class="decision-value">{zone_rec['room']} ({zone_rec['zone']})</span>
            </div>
            <div class="decision-row">
                <span class="decision-label">Applied Setpoint</span>
                <span class="decision-value">{zone_rec['setpoint']:.1f}°C</span>
            </div>
            <div class="decision-row">
                <span class="decision-label">Current PMV</span>
                <span class="decision-value">{zone_rec['pmv']:+.2f} &middot; {zone_rec['comfort_label']}</span>
            </div>
            <div class="decision-row">
                <span class="decision-label">Occupancy</span>
                <span class="decision-value">{"Occupied" if zone_rec['occupied'] else "Unoccupied"}</span>
            </div>
            <div class="decision-row full">
                <span class="decision-label">Reason</span>
                <span class="decision-value">{reason}</span>
            </div>
            <div class="decision-row full">
                <span class="decision-label">Action Taken</span>
                <span class="decision-value">{action}</span>
            </div>
        </div>
    </div>
    """), unsafe_allow_html=True)
    st.caption("Decision generated by the local LLM using live EnergyPlus Runtime API telemetry, cross-checked against guardrail events.")


def render_legend():
    items = "".join(
        f'<span class="legend-item"><span class="legend-dot" style="background:{color}"></span>{label}</span>'
        for _, label, color in COMFORT_BANDS
    )
    st.markdown(_compact_html(f'<div class="legend-row">{items}</div>'), unsafe_allow_html=True)


def build_floorplan_svg(template: str, zone_records: list[dict]) -> str:
    svg = template
    for i, rec in enumerate(zone_records, start=1):
        occ_color = COLOR_SAGE_ON_INK if rec["occupied"] else "rgba(237,233,224,0.28)"
        ring_opacity = "0.35" if rec["occupied"] else "0"
        svg = svg.replace(f"{{Z{i}_TEMP}}", f"{rec['temp']:.1f}°C")
        svg = svg.replace(f"{{Z{i}_PMV}}", f"{rec['pmv']:+.2f}")
        svg = svg.replace(f"{{Z{i}_SETPOINT}}", f"{rec['setpoint']:.1f}°C")
        svg = svg.replace(f"{{Z{i}_OCC_COLOR}}", occ_color)
        svg = svg.replace(f"{{Z{i}_OCC_RING_OPACITY}}", ring_opacity)

    # Room background tint by comfort band — the comfort-band color reused
    # at low opacity directly on the dark twin canvas (see COLOR_INK).
    rects = [
        ('1 1 398 193'),
        ('401 1 398 193'),
        ('1 196 398 188'),
        ('401 196 398 188'),
        ('1 386 798 192'),
    ]
    bg_markup = "".join(
        f'<rect x="{geom.split()[0]}" y="{geom.split()[1]}" width="{geom.split()[2]}" height="{geom.split()[3]}" '
        f'fill="{rec["comfort_color"]}" opacity="0.24"/>'
        for geom, rec in zip(rects, zone_records)
    )
    svg = svg.replace("><defs>", f">{bg_markup}<defs>", 1)
    print("><defs>" in svg_template)
    return svg


def telemetry_card(icon: str, label: str, value: str, dim: bool = False) -> str:
    value_class = "tel-value dim" if dim else "tel-value"
    return _compact_html(f"""
    <div class="tel-card">
        <div class="tel-label">{icon}{label}</div>
        <div class="{value_class}">{value}</div>
    </div>
    """)


def render_telemetry_row(latest: pd.Series, zone_records: list[dict]):
    avg_temp = sum(r["temp"] for r in zone_records) / len(zone_records)
    avg_pmv = sum(r["pmv"] for r in zone_records) / len(zone_records)
    occupied = sum(1 for r in zone_records if r["occupied"])
    cooling_zones = sum(1 for r in zone_records if r["temp"] > r["setpoint"] + 0.2)
    


    cards = [
        telemetry_card(ICON_CPU,"Controller","ACTIVE" if live else "IDLE"),
        telemetry_card(ICON_BOLT, "HVAC Power", f"{latest['facility_kw']:.2f} kW"),
        telemetry_card(ICON_THERMO, "Avg Zone Temp", f"{avg_temp:.1f}°C"),
        telemetry_card(ICON_SNOWFLAKE, "Cooling Demand", f"{cooling_zones} / {len(zone_records)} zones"),
        telemetry_card(ICON_GAUGE, "Average PMV", f"{avg_pmv:+.2f}"),
        telemetry_card(ICON_USERS, "Occupancy", f"{occupied} / {len(zone_records)} zones"),
    ]
    st.markdown(_compact_html(f'<div class="tel-row">{"".join(cards)}</div>'), unsafe_allow_html=True)
    

def render_zone_table(zone_records):
    df = pd.DataFrame([
        {
            "Zone": z["room"],
            "Temperature (°C)": round(z["temp"], 1),
            "PMV": round(z["pmv"], 2),
            "Setpoint (°C)": round(z["setpoint"], 1),
            "Occupied": "Yes" if z["occupied"] else "No",
            "Status": z["comfort_label"],
        }
        for z in zone_records
    ])

    st.dataframe(df, use_container_width=True, hide_index=True)
def render_power_timeline(df: pd.DataFrame):
    window = df.tail(150).reset_index(drop=True)
    rolling = window["facility_kw"].rolling(window=10, min_periods=1).mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=window.index, y=window["facility_kw"],
        mode="lines", name="Facility Power",
        line=dict(color=COLOR_STEEL, width=1.8, shape="spline", smoothing=0.3),
        hovertemplate="Step %{x}<br>%{y:.2f} kW<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=window.index, y=rolling,
        mode="lines", name="Rolling Avg (10-step)",
        line=dict(color=COLOR_TEXT_TERTIARY, width=1.2, dash="dot"),
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=[window.index[-1]], y=[window["facility_kw"].iloc[-1]],
        mode="markers", name="Current",
        marker=dict(color=COLOR_SAGE, size=8, line=dict(color=COLOR_PANEL, width=2)),
        hovertemplate="Current: %{y:.2f} kW<extra></extra>",
    ))
    fig.update_layout(
    height=320,
    margin=dict(l=10, r=10, t=10, b=10),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(
        family=FONT_UI,
        color=COLOR_TEXT_SECONDARY,
        size=12
    ),
    showlegend=True,
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.0,
        xanchor="left",
        x=0,
        bgcolor="rgba(0,0,0,0)",
        font=dict(
            color=COLOR_TEXT_PRIMARY,
            size=12
        )
    ),
    xaxis=dict(
        title="Simulation Time Step",
        gridcolor=COLOR_BORDER,
        zeroline=False,
        color=COLOR_TEXT_PRIMARY
    ),
    yaxis=dict(
        title="Power (kW)",
        gridcolor=COLOR_BORDER,
        zeroline=False,
        color=COLOR_TEXT_PRIMARY
    ),
    hovermode="x unified",
)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
st.set_page_config(page_title="EcoLoop Building Energy Management", page_icon=":material/thermostat:", layout="wide")
st_autorefresh(interval=3000, key="refresh")
inject_theme()

ai_df = load_csv(AI_LOG_PATH)
if ai_df is None:
    st.info("Waiting for live simulation data...")
    st.stop()

occupied_rows = ai_df[
    ai_df.filter(like="_occupancy").sum(axis=1) > 0
]

latest = occupied_rows.iloc[-1] if not occupied_rows.empty else ai_df.iloc[-1]
zone_records = build_zone_records(latest)
live = is_feed_live(AI_LOG_PATH)

render_header(latest, live)
baseline_df = load_csv(BASELINE_LOG_PATH)
baseline_energy = baseline_df["facility_kw"].sum()
ai_energy = ai_df["facility_kw"].sum()

energy_saved = baseline_energy - ai_energy
saving_pct = (energy_saved / baseline_energy) * 100
# Approximate commercial electricity price
COST_PER_KWH = 0.12      # USD

# Approximate grid emission factor
CO2_PER_KWH = 0.40        # kg CO₂

cost_saved = energy_saved * COST_PER_KWH
co2_saved = energy_saved * CO2_PER_KWH
occupied_timesteps = 0
comfortable_timesteps = 0

for zone in ZONES:
    occ = ai_df[f"{zone}_occupancy"] > 0
    pmv = ai_df[f"{zone}_pmv"].between(-0.5, 0.5)

    occupied_timesteps += occ.sum()
    comfortable_timesteps += (occ & pmv).sum()

comfort_pct = (
    100 * comfortable_timesteps / occupied_timesteps
    if occupied_timesteps
    else 100
)
render_kpi_row(
    latest,
    zone_records,
    live,
    saving_pct,
    energy_saved,
    cost_saved,
    co2_saved,
)
render_section_title(1, "Runtime Controller Decision")
guardrail_df = load_csv(GUARDRAIL_LOG_PATH)
priority = select_priority_zone(zone_records)
guardrail_action = find_guardrail_action(guardrail_df, int(latest["callback"]), priority["zone"])
action_text = guardrail_action or (
    f"Setpoint held at {priority['setpoint']:.1f}°C by runtime controller to correct thermal comfort deviation."
)
render_decision_panel(priority, build_decision_reason(priority), action_text)

render_section_title(2, "AI vs Baseline &mdash; Energy Consumption")

if baseline_df is not None:
    baseline_energy = baseline_df["facility_kw"].sum()

    ai_energy = ai_df["facility_kw"].sum()

    render_comparison_card(
     baseline_energy,
     ai_energy
    )
else:
    st.info(f"Baseline log not found at {BASELINE_LOG_PATH}")

for z in zone_records:
    print(
        z["room"],
        "PMV:", z["pmv"],
        "Band:", z["comfort_label"],
        "Color:", z["comfort_color"],
    )

render_section_title(3, "Building Digital Twin")
render_legend()
svg_template = load_svg_template(FLOORPLAN_SVG_PATH)
floorplan_svg = build_floorplan_svg(svg_template, zone_records)
st.markdown(_compact_html(f'<div class="twin-frame">{floorplan_svg}</div>'), unsafe_allow_html=True)
render_zone_table(zone_records)
render_section_title(4, "Current Runtime Telemetry")
render_telemetry_row(latest, zone_records)

render_section_title(5, "Facility Power Timeline")
render_power_timeline(ai_df)
with open("debug_floorplan.svg", "w", encoding="utf-8") as f:
    f.write(floorplan_svg)