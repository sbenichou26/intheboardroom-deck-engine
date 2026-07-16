import streamlit as st
import streamlit.components.v1 as components
from anthropic import Anthropic
import os
import re
import sys
import json
import base64
from io import BytesIO

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# ============================================================================
# In The Boardroom | Deck Intelligence Engine  (v3)
#
# CHANGES IN THIS VERSION:
#
# 1) WHITE INTERFACE. Clean white background so the intheboardroom logo (black
#    wordmark) reads properly. Navy/accent-blue used as accents only.
#
# 2) PDF EXPORT. Two export paths:
#    - Download the raw HTML deck (as before).
#    - "Open print view" opens the deck in a new tab with a print stylesheet
#      (landscape, one slide per page, no page breaks inside slides), so the
#      browser's own Print > Save as PDF produces a clean deck PDF. This is
#      done browser-side on purpose: it needs no extra system dependency
#      (wkhtmltopdf / Chrome headless) on the user's machine.
#
# 3) COMPREHENSIVE, DD-DRIVEN RESEARCH SCOPE.
#    The research checklist below is derived from a real football M&A due
#    diligence index. IMPORTANT DISTINCTION, and the reason the checklist is
#    split in two: a due diligence index lists documents a SELLER hands over
#    in a private data room (player salaries, release clauses, cap table,
#    shareholder agreements, general ledger, board minutes, DNCG
#    correspondence, ongoing litigation...). None of that is public. Asking a
#    web-research agent to "fill in" those sections is precisely what causes
#    fabrication.
#
#    So: PUBLIC_SCOPE lists what is genuinely researchable from public
#    sources and must be covered in depth. NON_PUBLIC_SCOPE lists what cannot
#    be sourced publicly â the model must NOT invent it, and instead surfaces
#    it on a final "Information Requests" slide as items to request in the
#    data room. For a fund, that slide is a credibility signal, not a gap.
#
# 4) STREAMING (REQUIRED). With a 32k-token output and up to 40 web searches,
#    a generation routinely exceeds the SDK's 10-minute ceiling for
#    non-streaming calls, which raises:
#      ValueError: Streaming is required for operations that may take longer
#      than 10 minutes.
#    The generation call therefore uses client.messages.stream(). This also
#    lets the UI show live progress (searches run, HTML written) instead of a
#    blind spinner.
# ============================================================================

st.set_page_config(
    page_title="In The Boardroom",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="collapsed"
)

NAVY = "#0D0A27"
BLUE = "#1234FF"
INK = "#1A1A2E"
MUTE = "#6E6E8A"
LINE = "#E4E4EF"
CARD = "#F6F7FB"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "template_light.html")


def load_template():
    if not os.path.exists(TEMPLATE_PATH):
        return None
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def load_logo_b64():
    p = os.path.join(BASE_DIR, "logo_itbr.b64.txt")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return f.read().strip()
    p = os.path.join(BASE_DIR, "logo_itbr.png")
    if os.path.exists(p):
        with open(p, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return None


LOGO_B64 = load_logo_b64()

# --- White, professional interface ------------------------------------------
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    html, body, [data-testid="stAppViewContainer"] {{
        font-family: 'Inter', sans-serif;
        background-color: #FFFFFF !important;
        color: {INK} !important;
    }}
    [data-testid="stHeader"] {{ background-color: #FFFFFF !important; }}

    .itbr-header {{
        display: flex; align-items: center; gap: 18px;
        padding: 6px 0 26px 0;
        border-bottom: 1px solid {LINE};
        margin-bottom: 30px;
    }}
    .itbr-header img {{ height: 44px; }}
    .itbr-eyebrow {{
        color: {BLUE}; font-size: 11px; font-weight: 700;
        letter-spacing: 0.22em; text-transform: uppercase; margin-bottom: 5px;
    }}
    .itbr-title {{
        color: {NAVY}; font-size: 26px; font-weight: 800; margin: 0;
    }}
    .itbr-subtitle {{ color: {MUTE}; font-size: 14px; margin-bottom: 26px; }}

    .stTextInput label {{
        color: {NAVY} !important; font-size: 11px !important; font-weight: 700 !important;
        letter-spacing: 0.09em; text-transform: uppercase;
    }}
    .stTextInput input {{
        background-color: #FFFFFF !important;
        border: 1.5px solid {LINE} !important;
        color: {INK} !important;
        border-radius: 6px !important;
        padding: 0.75rem !important;
    }}
    .stTextInput input:focus {{
        border-color: {BLUE} !important;
        box-shadow: 0 0 0 1px {BLUE} !important;
    }}

    /* Buttons: force white text on the blue/navy fills across every state.
       Streamlit re-applies its own text colour on hover/focus/active, which is
       what made the labels render black and unreadable. The selectors below
       (including the nested <p>, which Streamlit uses for the label) override
       that consistently. */
    .stButton>button,
    .stButton>button:hover,
    .stButton>button:focus,
    .stButton>button:active,
    .stButton>button:focus:not(:active) {{
        background-color: {BLUE} !important;
        color: #FFFFFF !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        padding: 0.65rem 1.5rem !important;
        border: none !important;
        box-shadow: none !important;
    }}
    .stButton>button p,
    .stButton>button span,
    .stButton>button div {{
        color: #FFFFFF !important;
        font-weight: 600 !important;
    }}
    .stButton>button:hover {{ filter: brightness(1.12); }}

    .stDownloadButton>button,
    .stDownloadButton>button:hover,
    .stDownloadButton>button:focus,
    .stDownloadButton>button:active,
    .stDownloadButton>button:focus:not(:active) {{
        background-color: {NAVY} !important;
        color: #FFFFFF !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        padding: 0.65rem 1.5rem !important;
        border: none !important;
        box-shadow: none !important;
    }}
    .stDownloadButton>button p,
    .stDownloadButton>button span,
    .stDownloadButton>button div {{
        color: #FFFFFF !important;
        font-weight: 600 !important;
    }}
    .stDownloadButton>button:hover {{ filter: brightness(1.25); }}

    .itbr-confirm-box {{
        background-color: {CARD}; border: 1px solid {LINE};
        border-radius: 8px; padding: 18px 22px; margin: 14px 0;
    }}
    .itbr-confirm-label {{
        color: {MUTE}; font-size: 10px; font-weight: 700;
        letter-spacing: 0.11em; text-transform: uppercase; margin-bottom: 5px;
    }}
    .itbr-confirm-name {{ color: {NAVY}; font-size: 20px; font-weight: 700; }}
    .itbr-confirm-note {{ color: {MUTE}; font-size: 13px; margin-top: 6px; }}

    div[data-testid="stMarkdownContainer"] p {{ color: {INK}; }}
    .itbr-footer {{
        text-align: center; margin-top: 60px; color: {MUTE};
        font-size: 11px; letter-spacing: 0.05em;
    }}
</style>
""", unsafe_allow_html=True)

logo_tag = f'<img src="data:image/png;base64,{LOGO_B64}" />' if LOGO_B64 else ""
st.markdown(f"""
<div class="itbr-header">
    {logo_tag}
    <div>
        <div class="itbr-eyebrow">Deck Intelligence Engine</div>
        <div class="itbr-title">M&amp;A Asset Advisory</div>
    </div>
</div>
<div class="itbr-subtitle">Sourced research only. Every figure traceable to a public primary source. What cannot be sourced is listed as an information request, never invented.</div>
""", unsafe_allow_html=True)

# ============================================================================
# PROMPTS
# ============================================================================

IDENTIFY_PROMPT = """You resolve a user's short, possibly informal input into the precise
sports entity they mean (a club, league, federation, or competition), so a downstream
research process can proceed without ambiguity.

Handle abbreviations, alternate spellings, missing or extra hyphens, and casing variants
as the same entity. For example "psg", "paris saint germain", and "Paris Saint-Germain"
all refer to the same football club and resolve to its correct official name.

Respond with ONLY a JSON object, no other text:
{
  "canonical_name": "the precise official name of the entity",
  "entity_type": "club" | "league" | "federation" | "competition" | "other",
  "confidence": "high" | "low",
  "note": "if confidence is low, a short note on the ambiguity; otherwise empty string"
}

If the input is genuinely ambiguous (it could refer to more than one distinct
organization), set confidence to "low" and explain briefly rather than guessing.
"""

SYSTEM_INSTRUCTIONS = """You are the M&A intelligence platform for "intheboardroom", producing
institutional-grade Discussion Materials on sports assets for investment funds. Style:
cold, analytical, corporate English, in the register of a sell-side bank memo.

===========================================================================
PRINCIPLE ZERO - INTEGRITY. THIS OVERRIDES EVERYTHING ELSE.
===========================================================================
You have a web_search tool. You MUST use it before writing ANY factual claim involving a
number, name, date, ownership stake, audience figure, follower count, contract value, or
transaction value. Never rely on training knowledge for such claims.

You are strictly forbidden from inventing, estimating, extrapolating, or guessing any data
point. If, after real searches, a data point is not publicly available, you OMIT that line
or block entirely. Never write a placeholder or an estimated figure in its place. A
shorter, fully-sourced slide is always better than a complete but partly invented one.

Prefer primary sources: audited annual accounts, DNCG and league financial reports, UEFA
benchmarking reports, official club/league communications, company registries, regulatory
filings, stock exchange filings. Wikipedia and aggregators are a starting point to locate
a primary source, never a final citation. Corroborate material figures across at least two
independent sources where feasible.

SOURCE HIERARCHY FOR FINANCIAL FIGURES - STRICT ORDER, NOT A SUGGESTION.
For every financial figure you must work down this ladder, and you must exhaust each rung
before dropping to the next:

  TIER 1 (primary, always try first):
    - The club's own filed statutory accounts / annual report / financial statements
    - THE CLUB'S OWN WEBSITE AND PRESS RELEASES. Clubs routinely publish their headline
      results (revenue, revenue split, wage ratio) in a press release before, or instead
      of, filing detailed public accounts. ALWAYS search the club's own site explicitly
      (e.g. site:psg.fr, "[club] record revenue press release", "[club] resultats
      financiers"). This has been missed before: a deck cited a blog's reconstruction for
      revenue while the club itself had published the figure on its own website.
    - For French clubs: the DNCG annual report, and the LFP's published club accounts
    - For listed entities or listed parents: regulatory filings
    - UEFA club licensing / benchmarking reports

  TIER 2 (reputable secondary, acceptable with attribution):
    - Deloitte Football Money League, Deloitte Annual Review of Football Finance
    - KPMG Football Benchmark
    - Major financial press reporting a figure and naming its source (FT, L'Equipe,
      Les Echos, Reuters)

  TIER 3 (analytical reconstructions - LAST RESORT ONLY):
    - Independent analysts and blogs that reconstruct a P&L from statutory accounts
      (e.g. Swiss Ramble), aggregator sites, Transfermarkt valuations

RULES:
- Do NOT build the financial slides on a Tier 3 source if a Tier 1 source exists. Search
  properly for the filed accounts first. Searching once and giving up is not exhausting a
  rung.
- If you end up using a Tier 2 or Tier 3 figure, you MUST label it inline as such, e.g.
  "per Deloitte Money League" or "analytical reconstruction per Swiss Ramble, not the
  club's own segment labels".
- Never present a Tier 3 reconstruction as if it were the club's reported accounts.
- If Tier 1 figures genuinely cannot be found, say so explicitly on the slide and in the
  Information Requests slide ("statutory accounts not publicly filed / not located; figures
  below are an analytical reconstruction"). A fund reader needs to know the provenance of a
  P&L, because they will underwrite against it.
- Where a Tier 1 and a Tier 3 figure disagree, use Tier 1 and note the discrepancy.

Distinguish clearly between a hard reported figure and a third-party estimate. If a number
is a modeled estimate (e.g. a brand valuation from a consultancy, a market-value figure
from Transfermarkt), attribute it explicitly as such ("per Transfermarkt", "per Deloitte
Football Money League") rather than presenting it as a reported fact.

PERIOD CONSISTENCY - THIS IS A HARD RULE, NOT A STYLE PREFERENCE.
Never mix figures from different fiscal years within the same slide, the same table, or
the same chart. Mixing a 2023-24 revenue with a 2024-25 wage bill produces a ratio that
is simply wrong, and a reader cannot detect it. Rules:
- Identify the most recent fiscal year for which a COMPLETE set of figures is published,
  and build the financial slides on that year.
- Label the period explicitly on every financial slide, table and chart (e.g. "FY2024-25,
  audited"). A number without its period is not usable.
- If one metric is only available for an older year than the others, either omit it, or
  place it in a clearly separated block with its own period label. Never silently slot it
  in beside more recent figures.
- Where you show a trend across years, every series in that chart must use the same year
  definitions.
- If the club's most recent published accounts are older than its most recent reported
  revenue headline, trust the accounts for the financial slides and note the discrepancy
  rather than blending the two.

INTERNAL CONSISTENCY - ONE VALUE PER METRIC. THIS IS A HARD RULE.
A given metric must carry the SAME number everywhere it appears in the deck. Decide each
figure once (e.g. FY2024-25 revenue = 837), then reuse that exact value verbatim on every
slide, chart, KPI block and in the executive summary. Never show 806 on one slide and 810
on another for the same metric and period. The same holds for names, dates and
percentages. Before you output the deck, RE-READ IT and reconcile every figure that
appears more than once: they must match to the digit. Do not repeat the same fact, bullet
or paragraph on multiple slides either: say each thing once, on the slide where it belongs.
Contradictory or duplicated numbers destroy a memo's credibility faster than a missing one.

===========================================================================
RESEARCH SCOPE - PUBLIC (COVER THESE IN DEPTH)
===========================================================================
This checklist is derived from a real football M&A due diligence index. The following are
genuinely researchable from public sources. Cover each one that has verifiable data,
each as its own slide or as a substantial block within a slide:

EXECUTIVE SUMMARY (REQUIRED - the FIRST content slide, right after the agenda)
A one-slide synthesis a fund partner reads in 60 seconds:
- One or two sentences on what the asset is and the investment angle (why look at it now).
- A KPI row with the headline financials for the most recent COMPLETE year, period
  labelled: revenue, wage-to-revenue ratio, net result, squad market value, stadium
  capacity. Use only figures you actually sourced.
- 3 to 5 "key points" bullets: ownership / sale context, revenue trajectory, main
  strengths, and the single principal risk.
Every number here MUST match the detailed slides exactly (see INTERNAL CONSISTENCY). End
the slide with a short source-line, e.g. "Figures sourced on the detailed slides that
follow", plus the primary source of the headline revenue figure.

CORPORATE & GOVERNANCE
- Legal entity, corporate structure, group organigram, subsidiaries
- Shareholders and ownership stakes (from company registries, official announcements)
- Board, executive leadership, key officers
- Recent capital increases or ownership changes, if publicly announced

NO REDUNDANCY RULE (applies everywhere, and especially to the ownership slide):
State each fact ONCE. Do not restate the same shareholding percentages in a table, then
again in prose, then again in a KPI block on the same slide. Repetition pads the slide
without adding information, and a fund reader reads it as padding.
If a slide feels thin after stating the facts once, do not pad it: go find more. For the
ownership slide, genuinely additive material includes: the history of ownership changes
with dates and the price paid at each step, prior valuations of the club and who set them,
the identity and background of the ultimate beneficial owner, any shareholder agreement
terms that were publicly reported, any publicly reported approach or bid that did not
complete, the ownership structure of the parent vehicle, and any stated intention of the
owner regarding sale or investment. If after real searching there is genuinely nothing
more, make the slide shorter. A short honest slide beats a padded one.

FINANCIAL PROFILE
- Annual accounts across the last available years: revenue, EBITDA, net result
- Revenue split by line: matchday, broadcasting, sponsorship, merchandising, other
- Wage bill and wage-to-revenue ratio
- Net debt, equity position
- DNCG / league regulatory financial position where reported
- Player trading result (transfer gains/losses) where reported

REVENUE LINES (each in detail)
- Revenue breakdown by line, at the FINEST GRANULARITY THE CLUB ACTUALLY PUBLISHES.
  Most clubs publish four lines: matchday, broadcasting, sponsorship/commercial, and
  merchandising, sometimes with player trading shown separately. Some publish more detail
  (ticketing vs season tickets vs hospitality vs F&B). Report whatever detail is genuinely
  published. CRITICAL: if the club only discloses an aggregate "matchday" figure, do NOT
  split it into invented ticketing / hospitality / F&B sub-figures. Report the aggregate.
  Fabricating a plausible-looking sub-split is exactly the failure mode this system exists
  to prevent.
  Show this breakdown for at least two periods where available, so the shift over time is
  visible, and chart it as a stacked or grouped bar (see CHARTS).
- REVENUE ATTRIBUTION IN PERCENT. For each revenue line, state BOTH the absolute figure AND
  its share of total revenue as a percentage, for the most recent complete year (e.g.
  "Broadcasting EUR 245m, 29% of revenue"). A fund reads the revenue mix in percentages.
  Compute each percentage from the sourced absolute figures (line / total), and make sure
  they sum to ~100%. If a line is not disclosed, do not infer its percentage. Carry these
  percentages into the revenue-split chart's legend, and consider a dedicated "revenue mix"
  view (donut or 100%-stacked bar) for the latest year.
- Matchday: stadium capacity, average attendance, occupancy rate, season ticket numbers,
  ticket pricing where published, hospitality offering
- Broadcasting: domestic league distribution, European competition revenue, international
  rights where reported
- Sponsorship: named sponsors, kit supplier, shirt sponsor, deal values and durations
  where publicly reported, sponsorship portfolio breadth
- Merchandising and retail: kit supplier deal, retail footprint, e-commerce, licensing
- Digital and media: owned OTT/streaming, YouTube and content channels, digital revenue
  where reported

SPORTING PERFORMANCE (dedicated slide)
- League finishes across recent seasons, points, and position (chart these)
- European competition participation and results by season
- Trophies won, with dates
- Current-season standing where relevant
- Key performance context that bears on revenue: European qualification is a revenue
  driver, so tie sporting results to their financial consequence where the link is
  documented

CLUB HISTORY TIMELINE (REQUIRED - a dedicated slide, using the template's .timeline component)
This slide is MANDATORY in every deck: do not skip it. A chronological timeline of the
defining moments of the club, with 6 to 10 entries mixing:
- Corporate: foundation, changes of ownership, capital increases, major commercial deals,
  stadium moves or builds
- Sporting: major trophies, historic European runs, promotions/relegations
- People: landmark players, defining managers, key executives
Every entry must have a real, sourced date. This slide is what gives a reader the shape of
the asset in ten seconds, so choose genuinely defining moments, not filler.

THE CITY / LOCAL MARKET (REQUIRED - a dedicated slide)
Context on the club's home city and region, because it frames commercial upside:
- Population of the city AND its metropolitan area, with the source and year.
- Local economy: main industries, notable local companies (potential sponsors), income
  level or GDP where reported.
- A brief history and cultural identity of the city, and its relationship to the club.
- Regional reach: how large a fanbase catchment the city and region represent.
Attribute every figure (INSEE or the national statistics office, city hall, official
economic data) with its year. Chart the population where a comparative or multi-year
sourced figure exists. Do not invent demographic or economic figures: omit what you cannot
source.

SPORTING
- Squad composition, squad size, average age
- Squad market value and its trend (attributed to the source, e.g. Transfermarkt)
- Contract expiry profile of key players (public contract end dates)
- Transfer history: notable purchases, sales, net transfer spend by window/season
- Academy output and notable academy-produced players
- Head coach and sporting leadership, recent turnover

STADIUM & INFRASTRUCTURE
- Stadium: name, capacity, ownership vs lease, any concession or municipal agreement
  publicly reported, renovation or new-build plans and their announced cost
- Training ground and academy facilities

FANBASE & DIGITAL AUDIENCE
- Social media followers by platform with the date observed, and growth if reported
- Membership / season ticket / official supporters club numbers
- Global fanbase figures ONLY where from a named study, cited as an estimate

MARKET & VALUATION CONTEXT
- League benchmark: where the club sits vs Ligue 1 / domestic peers on revenue, wages,
  attendance, squad value
- European benchmark where relevant (Deloitte Money League, UEFA benchmarking)
- Precedent transactions: comparable club acquisitions with disclosed values and dates
- Any publicly reported valuation of, or approach to, this club

REGULATORY
- DNCG status and any publicly reported decisions
- UEFA financial regulations status where reported
- Licensing status

===========================================================================
RESEARCH SCOPE - NON-PUBLIC (NEVER INVENT; SURFACE AS REQUESTS)
===========================================================================
The following exist in a private data room and are NOT publicly available. You must NOT
fabricate them. Do not create empty slides for them either. Instead, on a final
"Information Requests" slide, list the material items a buyer would need to request in
diligence, grouped logically. Typical items: individual player contracts (salary, bonuses,
release clauses, agent fees, image rights), full cap table and shareholder agreements,
board and general meeting minutes, general ledger and management accounts, budget and
forecast, intragroup contracts, ongoing litigation and prud'hommes, DNCG correspondence,
supplier and outsourcing contracts, CRM data (LTV, churn, segmentation), GPS/performance
data, insurance policies, tax audits.

Tailor that list to what you actually found missing for this specific asset. This slide is
a credibility signal: it shows what is known, what is not, and what must be obtained.

===========================================================================
PUNCTUATION - DASH HANDLING
===========================================================================
Convert dashes used as sentence punctuation (em dashes, or a hyphen surrounded by spaces
acting as a clause separator) into a colon (if the second clause defines or explains the
first) or a comma (otherwise). Do NOT alter hyphens that are part of a proper noun (e.g.
"Saint-Germain"), a compound term (e.g. "sell-side", "wage-to-revenue"), or a numeric or
season range (e.g. "2024-25", "10-15m"). Those hyphens carry real information and must be
preserved exactly. Never strip a hyphen from the name of the asset itself.

===========================================================================
CHARTS - REQUIRED, HAND-WRITTEN INLINE SVG ONLY
===========================================================================
The deck must contain charts. A wall of text and tables is not acceptable for an
investment memorandum.

TECHNICAL CONSTRAINT (non-negotiable): charts must be hand-written inline <svg> in the
HTML. Do NOT use Chart.js, D3, Plotly, or any JavaScript charting library, and do NOT
load any external script or CDN. The deck is a standalone file that gets downloaded and
printed to PDF: any JS-rendered chart would render as a blank box in the PDF and would
break offline. Inline SVG prints perfectly and needs nothing external.

DATA INTEGRITY RULE FOR CHARTS - THIS IS ABSOLUTE:
A chart may ONLY plot figures you actually sourced. Never invent a data point to complete
a series, never interpolate a missing year, never smooth or extend a trend. If you have
revenue for 2022, 2023 and 2025 but not 2024, plot three bars, not four. If a series is
too sparse to be meaningful, do not draw the chart at all: use a table or a KPI block
instead. A chart is a claim about data, and every point in it must be as defensible as a
sentence in the text.

NEVER LET A CHART'S SHAPE FORCE YOU TO INVENT. THIS IS THE MOST IMPORTANT RULE HERE.
Some chart types only "work" if you have a complete set of components: a bridge needs every
cost line, a pie needs every slice, a stacked bar needs every segment, a ratio needs both
numerator and denominator for the same period. When a chart type demands a component you
could not source, the temptation is to reconstruct that component so the picture holds
together. THAT IS FABRICATION, and it is more dangerous than plain text invention, because
a chart looks rigorous and its internal arithmetic can be made to close perfectly while
resting on numbers nobody published.

The rule: if a chart type requires a data point you did not source, you do not adjust the
data. You abandon that chart type and fall back to one that fits the data you actually
have. A single sourced bar with a KPI beside it beats a beautiful, balanced, invented
bridge. If in doubt, use a table of the figures you have, with each one's source.

WHERE CHARTS GO:
The reference template has placeholders marked [ IMAGE: chart ] and [ IMAGE: infographic ].
Replace those with real inline SVG charts. Add charts elsewhere too wherever a sourced
numeric series exists.

WHAT TO CHART (whenever the underlying data was actually found):
- REVENUE SPLIT ACROSS TWO PERIODS: the breakdown by line for the most recent year and an
  earlier comparison year, side by side (grouped or stacked bars), so the reader sees how
  the mix has shifted. Use only the granularity the club actually publishes.
- Revenue evolution across available years (column chart)
- Wage bill and wage-to-revenue ratio over time (columns plus a line for the ratio)
- EBITDA / net result trend (column chart, negatives below the axis)
- Attendance and occupancy trend (column chart)
- League position by season (line or column, inverted axis so 1st is highest)
- Squad market value evolution (line or column, attributed to its source)
- Net transfer spend by window (column chart with positive and negative bars)
- Social followers by platform (horizontal bar chart)
- Benchmark vs domestic league peers on revenue or wages (horizontal bar chart, the
  subject club highlighted in accent blue, peers in grey)

MANDATORY CHART GEOMETRY - USE THESE EXACT COORDINATES. DO NOT IMPROVISE THEM.
Charts looked misaligned in earlier decks because each one invented its own layout. Every
chart must therefore use this fixed frame:

  viewBox="0 0 600 340"     (always this, for every chart)
  Baseline (zero line):      y = 260
  Plot area top:             y = 60
  Plot area left edge:       x = 60
  Plot area right edge:      x = 580
  Max bar height:            200px  (a value equal to the series maximum = 200px tall)
  Unit label:                x=60,  y=30    (e.g. "EUR m, FY2024-25")
  Category labels:           y = 278, ALL of them, font-size 10, text-anchor="middle",
                             centred on their bar's x-centre
  Value labels above a bar:  y = (bar top y) - 8, font-size 11, text-anchor="middle"

  ALL category labels sit on the SAME baseline y=278. Never stagger them onto two rows to
  avoid overlap. If labels would collide, do one of these instead:
    - shorten the label ("Other opex" -> "Opex"), or
    - reduce bar width and increase spacing, or
    - if there are more than 7 bars, use the HORIZONTAL bar pattern instead.
  Staggered, overlapping or two-row category labels are a defect. Fix the layout, not the
  baseline.

  Bar layout for N bars: bar width W = min(62, floor(460 / N) - 20), and the first bar
  starts at x = 70, with each subsequent bar at x = 70 + i * (W + 22).

  Scaling: scale = 200 / max_absolute_value_in_the_series. Bar height = round(abs(value) *
  scale). A bar's y = 260 - height for positives. The axis ALWAYS starts at zero. When a
  chart compares several bars or periods (e.g. two years side by side), compute ONE shared
  scale from the single largest total across ALL bars, and apply that same scale to every
  bar, so their heights are directly comparable. Never rescale one bar independently: a
  bar with a smaller total must be visibly shorter, never taller.

STYLE RULES:
- Palette: primary series and the subject in var(--accent-blue) #1234FF; secondary series,
  peers and cost bars in #8A90C8; tertiary in #C7CCF5; a loss/negative result bar in
  #B3261E; text in #0D0A27; muted text in #6E6E8A; gridlines in #E4E4EF.
- Always label the numeric value directly on or above each bar/point. The deck is read in
  print and often in black and white: a chart that relies on colour alone, or that forces
  the reader to estimate a value against an axis, has failed.
- The unit label (top-left, at x=60 y=30) MUST be SHORT: only the unit and the period,
  e.g. "EUR m, FY2024-25" or "EUR m, FY2022-23 vs FY2024-25". Do NOT put source names,
  methodology or parentheticals inside it (never "(per Swiss Ramble)", "(reconstruction)"):
  a long unit label runs into the first bar. That attribution belongs on the .source-line.
- EVERY bar must carry its own numeric total, printed directly above it at y = (bar top) - 8.
  This applies to every bar of a grouped or stacked chart: if two period bars are shown,
  BOTH display their total on top, never just one.
- Every chart sits on a slide whose .source-line names the source of the plotted figures.

NO WATERFALL / BRIDGE CHARTS. DO NOT BUILD THEM.
A revenue-to-result bridge requires every cost line (wages, player amortisation, agent
fees, other opex, player trading) to be separately and reliably sourced. Clubs almost
never publish that breakdown. In practice, asking for a bridge pressures the model into
reconstructing a plausible-looking cost split so the arithmetic closes, which is
fabrication dressed up as analysis. It has already produced invented figures in this
system. Do not produce one, even if you think you can reconcile it.

If you have the revenue and a wage-to-revenue ratio but not the full cost stack, show a
simple column chart of revenue and state the wage ratio as a KPI beside it. That is the
honest, useful version.

CONCRETE PATTERN - column chart. Same frame: baseline y=260, labels y=278.
Bar height = round(value / max_value * 200), y = 260 - height. Here max is 972:
<svg viewBox="0 0 600 340" width="100%" style="max-height:300px;">
  <line x1="60" y1="260" x2="580" y2="260" stroke="#E4E4EF" stroke-width="1"/>
  <line x1="60" y1="60" x2="60" y2="260" stroke="#E4E4EF" stroke-width="1"/>
  <text x="60" y="30" font-size="11" fill="#6E6E8A" font-family="Arial">EUR m</text>
  <g>
    <rect x="90" y="125" width="60" height="135" fill="#1234FF"/>
    <text x="120" y="117" font-size="11" fill="#0D0A27" text-anchor="middle"
          font-family="Arial" font-weight="bold">654</text>
    <text x="120" y="278" font-size="10" fill="#6E6E8A" text-anchor="middle"
          font-family="Arial">2022-23</text>
  </g>
  <g>
    <rect x="180" y="94" width="60" height="166" fill="#1234FF"/>
    <text x="210" y="86" font-size="11" fill="#0D0A27" text-anchor="middle"
          font-family="Arial" font-weight="bold">806</text>
    <text x="210" y="278" font-size="10" fill="#6E6E8A" text-anchor="middle"
          font-family="Arial">2023-24</text>
  </g>
  <g>
    <rect x="270" y="60" width="60" height="200" fill="#1234FF"/>
    <text x="300" y="52" font-size="11" fill="#0D0A27" text-anchor="middle"
          font-family="Arial" font-weight="bold">972</text>
    <text x="300" y="278" font-size="10" fill="#6E6E8A" text-anchor="middle"
          font-family="Arial">2024-25</text>
  </g>
  <!-- repeat <g> for each further sourced year -->
</svg>

CONCRETE PATTERN - horizontal bar chart, subject highlighted vs peers.
EXCEPTION to the frame above: a horizontal chart has no zero baseline at y=260, because
the bars run left to right. It uses viewBox="0 0 600 340", rows every 36px starting at
y=20, a label column of 140px, and bar width = round(value / max_value * 380). Use this
whenever you have more than 7 categories, or long category names. Here max is 837:
<svg viewBox="0 0 600 340" width="100%" style="max-height:300px;">
  <text x="0" y="12" font-size="11" fill="#6E6E8A" font-family="Arial">EUR m, FY2024-25</text>
  <g font-family="Arial">
    <text x="0" y="42" font-size="12" fill="#0D0A27" font-weight="bold">Subject club</text>
    <rect x="140" y="30" width="380" height="18" fill="#1234FF"/>
    <text x="528" y="44" font-size="12" fill="#0D0A27" font-weight="bold">837</text>

    <text x="0" y="78" font-size="12" fill="#6E6E8A">Peer A</text>
    <rect x="140" y="66" width="116" height="18" fill="#8A90C8"/>
    <text x="264" y="80" font-size="12" fill="#6E6E8A">255</text>

    <text x="0" y="114" font-size="12" fill="#6E6E8A">Peer B</text>
    <rect x="140" y="102" width="91" height="18" fill="#8A90C8"/>
    <text x="239" y="116" font-size="12" fill="#6E6E8A">201</text>
  </g>
  <!-- repeat rows at y += 36 -->
</svg>

CONCRETE PATTERN - stacked bar, revenue split across TWO periods side by side.
Uses the mandatory frame: baseline y=260, labels y=278, tallest total = 200px.
Segments stack UPWARDS from the baseline. scale = 200 / largest_period_total. Here the
largest total is 837, so scale = 0.2389. Both bars sit on the same baseline:
<svg viewBox="0 0 600 340" width="100%" style="max-height:300px;">
  <line x1="60" y1="260" x2="580" y2="260" stroke="#E4E4EF" stroke-width="1"/>
  <text x="60" y="30" font-size="11" fill="#6E6E8A" font-family="Arial">EUR m, revenue by line</text>
  <g font-family="Arial">
    <!-- FY2022-23, total 654 -->
    <rect x="100" y="104" width="70" height="50" fill="#1234FF"/>
    <rect x="100" y="154" width="70" height="43" fill="#2838CC"/>
    <rect x="100" y="197" width="70" height="34" fill="#8A90C8"/>
    <rect x="100" y="231" width="70" height="29" fill="#C7CCF5"/>
    <text x="135" y="278" font-size="10" fill="#6E6E8A" text-anchor="middle">FY2022-23</text>
    <text x="135" y="96" font-size="11" fill="#0D0A27" text-anchor="middle" font-weight="bold">654</text>

    <!-- FY2024-25, total 837 -->
    <rect x="220" y="60"  width="70" height="59" fill="#1234FF"/>
    <rect x="220" y="119" width="70" height="70" fill="#2838CC"/>
    <rect x="220" y="189" width="70" height="40" fill="#8A90C8"/>
    <rect x="220" y="229" width="70" height="31" fill="#C7CCF5"/>
    <text x="255" y="278" font-size="10" fill="#6E6E8A" text-anchor="middle">FY2024-25</text>
    <text x="255" y="52" font-size="11" fill="#0D0A27" text-anchor="middle" font-weight="bold">837</text>
  </g>
  <!-- legend: state the value of every segment, for BOTH periods -->
  <g font-size="10" font-family="Arial">
    <rect x="360" y="60"  width="10" height="10" fill="#1234FF"/>
    <text x="376" y="69"  fill="#0D0A27">Broadcasting  210 -> 245</text>
    <rect x="360" y="80"  width="10" height="10" fill="#2838CC"/>
    <text x="376" y="89"  fill="#0D0A27">Sponsorship   180 -> 295</text>
    <rect x="360" y="100" width="10" height="10" fill="#8A90C8"/>
    <text x="376" y="109" fill="#0D0A27">Matchday      144 -> 167</text>
    <rect x="360" y="120" width="10" height="10" fill="#C7CCF5"/>
    <text x="376" y="129" fill="#0D0A27">Merchandising 120 -> 130</text>
  </g>
</svg>
Only use the line categories the club actually publishes. If it publishes four lines, show
four segments, not an invented eight.

Scale every bar honestly: bar length must be proportional to the value, and the axis must
start at zero. Never truncate an axis to exaggerate a difference.

===========================================================================
TEMPLATE - CLONE THE STRUCTURE, NEVER THE STYLE BLOCK
===========================================================================
You will be given the full HTML of intheboardroom's real template as reference.
- Never modify anything inside the <style>...</style> block. Copy it verbatim.
- Never modify, shorten, or replace the literal token PLACEHOLDER_IMAGE_DATA wherever it
  appears. Keep it exactly as-is, character for character. A separate process replaces it.
- The template's demonstration text ("PROJECT TITLE", "Highlight title goes here",
  "xxxxxxxxxxxxxxxxxxxxxx", "[ IMAGE: ... ]") is placeholder, not content. Replace every
  instance with real sourced content, or remove that element entirely.
- Specifically: placeholders marked [ IMAGE: chart ] and [ IMAGE: infographic ] must be
  replaced by a real inline SVG chart built from sourced figures (see the CHARTS section),
  not simply deleted, unless you genuinely found no numeric series for that slide.
  Placeholders for photos ([ IMAGE: full-bleed background photo ], [ IMAGE: photo grid ],
  [ IMAGE: photo strip ], [ IMAGE: subject / client logo ]) should be removed, since we
  cannot source real photography.

DARK SLIDES - IMPORTANT, THIS HAS GONE WRONG BEFORE.
Several template slides have a dark background BY DESIGN and expect a full-bleed photo on
top of it: .slide.cover (#1a1a1a), .slide.section-divider (#0a0a0a), .slide.agenda and
.slide.contact (navy). Because we cannot source photography, that photo placeholder gets
removed, and the slide then renders as a large EMPTY BLACK RECTANGLE. That is what has been
appearing in generated decks, and it looks broken.

Rules to prevent it:
- Keep the COVER, the AGENDA/SUMMARY, and the CONTACT slide. They are dark by design and
  they carry real text (title, contents list, contact block), so they read as intentional.
  Just make sure the text on them is white/light and actually present.
- SECTION DIVIDERS: keep them ONLY if they carry a large, legible section title in white on
  the dark background. A section divider with its title but no photo is fine and looks
  deliberate. A section divider with no title is an empty black slide: delete it.
- NEVER produce a slide whose entire content was an image placeholder. If removing the
  photo placeholder leaves a slide with no text, delete the whole slide.
- All body/content slides must be WHITE background with dark text. Do not put chart or
  table content on a dark slide.
- Every dark slide must have light text (#FFFFFF or #C7CCF5). Never dark text on a dark
  slide, and never light text on a white slide. Check the contrast of every slide you emit.
- Exception: the DISCLAIMER slide's legal boilerplate paragraphs are real fixed text. Keep
  them as written.
- Reuse the template's component patterns (kpi-grid, opp-grid, struct-table, gov-row,
  timeline, section-divider) as many times as needed. This is a LONG, comprehensive deck:
  expect roughly 15 to 25 slides for a well-documented club. Use section dividers to
  separate the major parts.
- Every content slide ends with a real, dated .source-line naming the actual sources used
  for that slide.
- Keep the .logo-chip element (with its untouched PLACEHOLDER_IMAGE_DATA) on every slide
  where the reference template has it.

===========================================================================
OUTPUT
===========================================================================
Output ONLY the complete HTML document, from <!DOCTYPE html> to </html>. No markdown
fences, no commentary. Do all your searches first; write the HTML only once research is
complete.
"""

# --- Print stylesheet injected into the deck for clean PDF export ------------
PRINT_CSS = """
<style id="itbr-print">
@media print {
  /* One page per slide, exactly the slide's 1280x720 px (16:9). */
  @page { size: 1280px 720px; margin: 0; }

  /* The deck's body is a flex column with gap:40px and padding:40px on a dark
     background. Left as-is when printing, those gaps and that padding push each
     slide down/right inside its page, so the bottom and right get clipped. Kill
     the flex layout for print so every slide maps 1:1 onto its own page. */
  html, body {
    background: #FFFFFF !important;
    margin: 0 !important;
    padding: 0 !important;
    display: block !important;
    gap: 0 !important;
    width: 1280px !important;
  }
  .slide {
    width: 1280px !important;
    height: 720px !important;
    margin: 0 !important;
    padding: 0 !important;
    box-shadow: none !important;
    overflow: hidden !important;
    flex-shrink: 0 !important;
    page-break-after: always;
    break-after: page;
    page-break-inside: avoid;
    break-inside: avoid;
  }
  .slide:last-child { page-break-after: auto; break-after: auto; }

  /* Print engines drop background colours by default, which would turn the dark
     cover/divider slides white (with invisible white text) and hide chart bars.
     Force every fill through. */
  * {
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }
  svg { page-break-inside: avoid; break-inside: avoid; }
}
</style>
"""


def add_print_css(html: str) -> str:
    """Inject the print stylesheet just before </head> so the browser's
    Print > Save as PDF produces one slide per landscape page."""
    if "</head>" in html:
        return html.replace("</head>", PRINT_CSS + "</head>", 1)
    return PRINT_CSS + html


# ============================================================================
# ACCESS GATE
#
# This app is deployed behind a PUBLIC URL (Streamlit Community Cloud gives no
# authentication by default). Every generation costs real money: up to 40 web
# searches plus a 32k-token Opus completion. Without a gate, anyone who finds
# the URL, including automated scanners that crawl public Streamlit apps, can
# run generations billed to our API key.
#
# So: nothing that touches the API runs until the password is entered. The
# password is read from the server-side secret APP_PASSWORD, never hardcoded.
# ============================================================================

def check_password() -> bool:
    """Gate the app behind a password held in server-side secrets."""
    expected = os.environ.get("APP_PASSWORD") or st.secrets.get("APP_PASSWORD", None)

    # If no password is configured, refuse to run rather than silently
    # exposing a billable app to the open internet.
    if not expected:
        st.error(
            "APP_PASSWORD is not configured. Set it in the app's secrets before "
            "using this deployment. The app will not run unprotected, because every "
            "generation is billed to the API key."
        )
        return False

    if st.session_state.get("auth_ok"):
        return True

    st.markdown("#### Access")
    pw = st.text_input("Password", type="password", key="pw_input")
    if st.button("Enter"):
        if pw == expected:
            st.session_state.auth_ok = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


if not check_password():
    st.markdown(
        '<div class="itbr-footer">In The Boardroom &middot; Institutional Platform &copy; 2026</div>',
        unsafe_allow_html=True,
    )
    st.stop()

# ============================================================================
# STATE
# ============================================================================

if "resolved" not in st.session_state:
    st.session_state.resolved = None
if "deck_html" not in st.session_state:
    st.session_state.deck_html = None

api_key = os.environ.get("ANTHROPIC_API_KEY") or st.secrets.get("ANTHROPIC_API_KEY", None)


def extract_client_materials(uploaded_files) -> str:
    """Read attached private files (txt/md/csv/pdf/docx) into plain text, to be
    injected into the generation prompt and labelled 'client-provided'. Best
    effort: an unreadable file is noted and skipped, never fatal."""
    parts = []
    for uf in uploaded_files or []:
        name = getattr(uf, "name", "file")
        ext = name.lower().rsplit(".", 1)[-1] if "." in name else ""
        try:
            data = uf.getvalue()
            if ext in ("txt", "md", "csv"):
                parts.append(f"--- {name} ---\n" + data.decode("utf-8", errors="replace"))
            elif ext == "pdf":
                import pypdf
                reader = pypdf.PdfReader(BytesIO(data))
                text = "\n".join((page.extract_text() or "") for page in reader.pages)
                parts.append(f"--- {name} ---\n" + text)
            elif ext == "docx":
                import docx
                doc = docx.Document(BytesIO(data))
                text = "\n".join(p.text for p in doc.paragraphs)
                parts.append(f"--- {name} ---\n" + text)
            else:
                parts.append(f"--- {name}: unsupported type, skipped ---")
        except Exception as e:
            parts.append(f"--- {name}: could not read ({type(e).__name__}); skipped ---")
    return "\n\n".join(parts).strip()


raw_input = st.text_input(
    "Target asset - club, league, or sports property",
    placeholder="e.g. PSG, Paris Saint-Germain, Stade Brestois, IOF...",
    key="raw_input",
)

uploaded_files = st.file_uploader(
    "Optional - attach private / data-room materials. Their figures are used but "
    "labelled 'Client-provided / data-room' in the deck, kept distinct from public sources.",
    type=["txt", "md", "csv", "pdf", "docx"],
    accept_multiple_files=True,
    key="uploads",
)
if uploaded_files:
    st.caption(
        f"{len(uploaded_files)} file(s) attached: "
        + ", ".join(f.name for f in uploaded_files)
    )

if st.button("Identify asset"):
    if not raw_input.strip():
        st.warning("Enter a club, league, or sports property first.")
    elif not api_key:
        st.error("No API key configured. Set ANTHROPIC_API_KEY as a server-side environment variable.")
    else:
        with st.spinner("Identifying the exact entity..."):
            try:
                client = Anthropic(api_key=api_key)
                resp = client.messages.create(
                    model="claude-sonnet-5",
                    max_tokens=500,
                    system=IDENTIFY_PROMPT,
                    messages=[{"role": "user", "content": raw_input.strip()}],
                )
                raw_text = "".join(
                    b.text for b in resp.content if getattr(b, "type", None) == "text"
                ).strip()
                raw_text = re.sub(r"^```(json)?\s*", "", raw_text)
                raw_text = re.sub(r"```\s*$", "", raw_text)
                st.session_state.resolved = json.loads(raw_text)
                st.session_state.deck_html = None
            except Exception as e:
                st.error("Could not identify the asset.")
                st.exception(e)

if st.session_state.resolved:
    r = st.session_state.resolved
    note_html = (
        f'<div class="itbr-confirm-note">{r.get("note", "")}</div>'
        if r.get("confidence") == "low" and r.get("note") else ""
    )
    st.markdown(f"""
    <div class="itbr-confirm-box">
        <div class="itbr-confirm-label">Understood as</div>
        <div class="itbr-confirm-name">{r.get('canonical_name', '')}</div>
        <div class="itbr-confirm-note">{r.get('entity_type', '').capitalize()}</div>
        {note_html}
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])
    with c1:
        confirm_clicked = st.button("Confirm and generate deck")
    with c2:
        if st.button("Not correct, retype above"):
            st.session_state.resolved = None
            st.rerun()

    if confirm_clicked:
        template_html = load_template()
        if not template_html:
            st.error(f"Template not found at {TEMPLATE_PATH}.")
            st.stop()

        progress_box = st.empty()
        status_box = st.empty()

        try:
            client = Anthropic(api_key=api_key)
            canonical_name = r.get("canonical_name", raw_input.strip())

            client_text = extract_client_materials(uploaded_files)
            MAX_CLIENT_CHARS = 40000
            truncated = len(client_text) > MAX_CLIENT_CHARS
            if truncated:
                client_text = client_text[:MAX_CLIENT_CHARS]
            client_block = ""
            if client_text:
                client_block = (
                    "\n\n=== CLIENT-PROVIDED / DATA-ROOM MATERIALS (PRIVATE) ===\n"
                    "These materials were supplied privately by the user. You MAY use their "
                    "figures and facts even though they are not public, BUT any slide that "
                    "uses them MUST carry a source-line reading 'Client-provided / data-room "
                    "material' (never present a private figure as a public source). Keep "
                    "public-sourced and client-provided figures distinguishable. All "
                    "integrity rules still apply: do not invent beyond what these materials "
                    "or public sources actually state; if a client figure conflicts with a "
                    "public one, use the client figure and note the discrepancy.\n"
                    + ("[Note: materials were truncated to fit.]\n" if truncated else "")
                    + "\n" + client_text
                    + "\n=== END CLIENT-PROVIDED MATERIALS ===\n"
                )

            user_prompt = (
                f'Target asset (confirmed): "{canonical_name}" '
                f'({r.get("entity_type", "entity")}).'
                + client_block
                + "\n\nProduce the comprehensive Discussion Materials deck. Reference "
                "template to clone (structure and CSS only):\n\n"
                + template_html
            )

            status_box.info(
                "Researching across corporate, financials, revenue lines, squad, "
                "stadium, fanbase, benchmarks and regulation. This runs many real web "
                "searches and can take 10+ minutes. Progress below."
            )

            # Streaming is REQUIRED here: this generation routinely exceeds the SDK's
            # 10-minute non-streaming ceiling (32k output tokens + up to 40 web
            # searches). Streaming also lets us surface live progress instead of a
            # blind spinner.
            chunks = []
            searches = 0
            with client.messages.stream(
                model="claude-opus-4-8",
                max_tokens=32000,
                system=SYSTEM_INSTRUCTIONS,
                tools=[
                    {"type": "web_search_20250305", "name": "web_search", "max_uses": 40}
                ],
                messages=[{"role": "user", "content": user_prompt}],
            ) as stream:
                for event in stream:
                    etype = getattr(event, "type", "")
                    if etype == "content_block_start":
                        block = getattr(event, "content_block", None)
                        if getattr(block, "type", "") == "server_tool_use":
                            searches += 1
                            progress_box.caption(
                                f"Web searches run: {searches} | "
                                f"HTML written: {sum(len(c) for c in chunks):,} chars"
                            )
                    elif etype == "text":
                        chunks.append(getattr(event, "text", ""))
                        if len(chunks) % 25 == 0:
                            progress_box.caption(
                                f"Web searches run: {searches} | "
                                f"HTML written: {sum(len(c) for c in chunks):,} chars"
                            )

                final_message = stream.get_final_message()

            html_result = "".join(
                b.text for b in final_message.content
                if getattr(b, "type", None) == "text"
            ).strip()
            html_result = re.sub(r"^```html\s*", "", html_result)
            html_result = re.sub(r"^```\s*", "", html_result)
            html_result = re.sub(r"```\s*$", "", html_result)

            if "<!DOCTYPE html>" not in html_result:
                status_box.empty()
                progress_box.empty()
                st.error("The model did not return a valid HTML document. Try again.")
                st.stop()

            if LOGO_B64:
                html_result = html_result.replace("PLACEHOLDER_IMAGE_DATA", LOGO_B64)

            html_result = add_print_css(html_result)

            st.session_state.deck_html = html_result
            st.session_state.deck_name = canonical_name

            status_box.empty()
            progress_box.empty()

        except Exception as e:
            status_box.empty()
            progress_box.empty()
            st.error("Generation failed. Full technical details below:")
            st.exception(e)
            st.stop()

# --- Result + exports --------------------------------------------------------
if st.session_state.deck_html:
    st.markdown("---")
    name = st.session_state.get("deck_name", "asset")
    slug = name.lower().replace(" ", "_")
    st.markdown(f"### Preview - {name}")

    e1, e2 = st.columns([1, 1])
    with e1:
        st.download_button(
            label="Download HTML deck",
            data=st.session_state.deck_html.encode("utf-8"),
            file_name=f"boardroom_deck_{slug}.html",
            mime="text/html",
        )
    with e2:
        # PDF export, browser-side so it needs no server dependency and keeps the
        # exact Chrome print rendering the deck's @media print CSS targets.
        # The old version used window.open("") + document.write, which Streamlit's
        # sandboxed component iframe blocks, so nothing happened. This version
        # builds a Blob URL (reliable) and opens it in a new tab that auto-launches
        # the print dialog; if the pop-up is blocked it downloads a print-ready
        # file instead, which prints itself when opened.
        autoprint = (
            "<script>window.addEventListener('load',function(){"
            "setTimeout(function(){window.print();},500);});</script>"
        )
        _deck = st.session_state.deck_html
        if "</body>" in _deck:
            print_html = _deck.replace("</body>", autoprint + "</body>", 1)
        else:
            print_html = _deck + autoprint
        deck_b64 = base64.b64encode(print_html.encode("utf-8")).decode("ascii")
        components.html(
            f"""
            <button id="pdfbtn" style="
                width:100%; padding:0.65rem 1.5rem; border:none; border-radius:6px;
                background:{NAVY}; color:#fff; font-weight:600; font-size:14px;
                font-family:Inter,sans-serif; cursor:pointer;">
                Save as PDF
            </button>
            <script>
            document.getElementById("pdfbtn").onclick = function() {{
                const bin = atob("{deck_b64}");
                const bytes = new Uint8Array(bin.length);
                for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
                const blob = new Blob([bytes], {{type: "text/html;charset=utf-8"}});
                const url = URL.createObjectURL(blob);
                const w = window.open(url, "_blank");
                if (!w) {{
                    const a = document.createElement("a");
                    a.href = url; a.download = "boardroom_deck_print.html";
                    document.body.appendChild(a); a.click(); a.remove();
                }}
            }};
            </script>
            """,
            height=52,
        )
        st.caption(
            "Opens the deck and launches the print dialog. For slides to fill each "
            "page: Destination 'Save as PDF', Margins 'None', Scale '100%' (or "
            "'Default', not 'Fit to page'). If a pop-up is blocked, a print-ready "
            "file downloads instead: open it and print with the same settings."
        )

    # --- Editable PowerPoint (.pptx) -----------------------------------------
    # Built on demand: a cheap structuring call (sonnet, no web search) turns the
    # finished deck into a JSON structure, which we render into native, editable
    # PowerPoint objects (text boxes, tables, charts). The HTML deck stays the
    # source of truth; this is a convenience export, so it runs only on click.
    if st.button("Build editable PowerPoint (.pptx)"):
        with st.spinner("Structuring the deck into editable PowerPoint (~20-40 s)..."):
            try:
                import pptx_export
                client = Anthropic(api_key=api_key)
                structure = pptx_export.deck_to_structure(client, st.session_state.deck_html)
                st.session_state.pptx_bytes = pptx_export.build_pptx(structure).getvalue()
                st.session_state.pptx_slug = slug
            except Exception as e:
                st.session_state.pptx_bytes = None
                st.error("PowerPoint build failed. Full technical details below:")
                st.exception(e)

    if st.session_state.get("pptx_bytes"):
        st.download_button(
            label="Download .pptx",
            data=st.session_state.pptx_bytes,
            file_name=f"boardroom_deck_{st.session_state.get('pptx_slug', slug)}.pptx",
            mime=("application/vnd.openxmlformats-officedocument."
                  "presentationml.presentation"),
        )
        st.caption(
            "Editable in PowerPoint / Keynote / Google Slides. Charts and tables are "
            "native objects, not images. Structured from the deck by the model, so "
            "verify the figures against the HTML deck before sending."
        )

    components.html(st.session_state.deck_html, height=760, scrolling=True)

st.markdown(
    '<div class="itbr-footer">In The Boardroom &middot; Institutional Platform &copy; 2026</div>',
    unsafe_allow_html=True,
)
