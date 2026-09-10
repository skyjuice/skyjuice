#!/usr/bin/env python3
"""Generate retro-CRT profile panels (SVG) for the skyjuice GitHub profile README.

Uses public-only GitHub data via the GraphQL API.
Token: GITHUB_TOKEN / GH_TOKEN env vars, or `gh auth token` locally.
"""

import json
import math
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

USER = "skyjuice"
ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")

# --- CRT palette ---------------------------------------------------------------
SCREEN = "#0b0803"   # near-black warm screen
PANEL = "#0f0a04"    # card background
BEZEL = "#1c150a"    # CRT casing
BORDER = "#3a2c10"   # dim border
BORDER_HOT = "#ffb000"  # amber border
AMBER = "#ffb000"    # phosphor amber
BRIGHT = "#ffd27f"   # warm white-amber
DIM = "#b37400"      # dim amber
MUTED = "#c9a35c"    # tan
FAINT = "#8a6a2a"    # faint amber
TRACK = "#2a1f0c"    # empty bar
GRAD_A = "#ffb000"
GRAD_B = "#ff6a00"
MONO = "'Courier New','IBM Plex Mono',Consolas,'Lucida Console',monospace"

FALLBACK_DESCRIPTIONS = {
    "dsh-open-ide": "Open a DeepSeek Harness session in your IDE or file manager — one-command dsh bundle plugin",
    "dsh-model-picker": "Enhanced model picker for DeepSeek Harness — favourites, search, free/paid pricing",
    "deepseek-harness": "DeepSeek Harness: Everything is a Plugin.",
}

QUERY = """
query {
  user(login: "%s") {
    name
    createdAt
    company
    location
    websiteUrl
    followers { totalCount }
    following { totalCount }
    repositories(first: 100, ownerAffiliations: [OWNER], privacy: PUBLIC, orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      nodes {
        name
        description
        stargazerCount
        forkCount
        isFork
        primaryLanguage { name color }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
    }
  }
}
""" % USER


def get_token() -> str:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok
    try:
        out = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except Exception:
        sys.exit("No GitHub token available (set GITHUB_TOKEN or run `gh auth login`)")


def graphql(token: str, query: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "skyjuice-profile-cards",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if "errors" in data:
        sys.exit(f"GraphQL errors: {data['errors']}")
    return data["data"]["user"]


# --- shared CRT helpers ---------------------------------------------------------

def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def fmt_num(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}m"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


def wrap(text: str, max_chars: int) -> list:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines[:3]


DEFS = """<defs>
<linearGradient id="grad" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0%" stop-color="{ga}"/><stop offset="100%" stop-color="{gb}"/>
</linearGradient>
<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">
  <rect width="4" height="1.6" fill="#000000" opacity="0.16"/>
</pattern>
<radialGradient id="vig" cx="50%" cy="42%" r="75%">
  <stop offset="55%" stop-color="#000000" stop-opacity="0"/>
  <stop offset="100%" stop-color="#000000" stop-opacity="0.55"/>
</radialGradient>
<filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
  <feGaussianBlur stdDeviation="2.6" result="b"/>
  <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>
</defs>""".format(ga=GRAD_A, gb=GRAD_B)


def overlay(w: int, h: int) -> str:
    """scanlines + vignette on top of a panel"""
    return (
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="url(#scan)"/>'
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="url(#vig)"/>'
    )


def panel_open(w: int, h: int, bezel: bool = False) -> str:
    fill, stroke = (BEZEL, BORDER) if bezel else (PANEL, BORDER)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" font-family="{MONO}">'
        f'<rect x="0" y="0" width="{w}" height="{h}" rx="6" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="1"/>'
    )


def title(w: int, text: str, cursor_x: int = 150) -> str:
    """amber glowing panel title with block cursor"""
    return (
        f'<text x="20" y="30" font-size="15" font-weight="700" fill="{AMBER}" '
        f'filter="url(#glow)">{esc(text)}</text>'
        f'<rect x="{cursor_x}" y="17" width="8" height="13" fill="{AMBER}" opacity="0.85"/>'
    )


def status_right(w: int, text: str, y: int = 28) -> str:
    return (
        f'<text x="{w-20}" y="{y}" font-size="10" fill="{FAINT}" text-anchor="end">'
        f"{esc(text)}</text>"
    )


# --- 5x5 pixel font --------------------------------------------------------------

FONT5 = {
    "A": ["01110", "10001", "11111", "10001", "10001"],
    "B": ["11110", "10001", "11110", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "11110", "10000", "11111"],
    "F": ["11111", "10000", "11110", "10000", "10000"],
    "G": ["01111", "10000", "10111", "10001", "01111"],
    "H": ["10001", "10001", "11111", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "10010", "01100"],
    "K": ["10001", "10010", "11100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001"],
    "O": ["01110", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "11110", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10011", "01111"],
    "R": ["11110", "10001", "11110", "10010", "10001"],
    "S": ["01111", "10000", "01110", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10101", "11011", "10001"],
    "X": ["10001", "01010", "00100", "01010", "10001"],
    "Y": ["10001", "01010", "00100", "00100", "00100"],
    "Z": ["11111", "00010", "00100", "01000", "11111"],
    "0": ["01110", "10011", "10101", "11001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00010", "00100", "01111"],
    "3": ["11110", "00001", "01110", "00001", "11110"],
    "4": ["00010", "00110", "01010", "11111", "00010"],
    "5": ["11111", "10000", "11110", "00001", "11110"],
    "6": ["01110", "10000", "11110", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000"],
    "8": ["01110", "10001", "01110", "10001", "01110"],
    "9": ["01110", "10001", "01111", "00001", "01110"],
    ".": ["00000", "00000", "00000", "00000", "00100"],
    "-": ["00000", "00000", "11111", "00000", "00000"],
    "_": ["00000", "00000", "00000", "00000", "11111"],
    " ": ["00000", "00000", "00000", "00000", "00000"],
}


def pixel_text(text: str, x: int, y: int, scale: int, color: str = AMBER) -> str:
    """render 5x5 pixel text as rects; returns svg fragment"""
    out = []
    for i, ch in enumerate(text.upper()):
        glyph = FONT5.get(ch, FONT5[" "])
        for row, line in enumerate(glyph):
            for col, bit in enumerate(line):
                if bit == "1":
                    px = x + i * 6 * scale + col * scale
                    py = y + row * scale
                    out.append(
                        f'<rect x="{px}" y="{py}" width="{scale}" height="{scale}" '
                        f'fill="{color}"/>'
                    )
    return "\n".join(out)


def pixel_width(text: str, scale: int) -> int:
    return len(text) * 6 * scale


# --- banner -----------------------------------------------------------------------

def banner() -> str:
    w, h = 800, 340
    word = "FAIZAN"
    scale = 12
    pw = pixel_width(word, scale)
    out = [panel_open(w, h, bezel=True), DEFS]
    # screen inset
    out.append(
        f'<rect x="16" y="16" width="{w-32}" height="{h-32}" rx="8" fill="{SCREEN}" '
        f'stroke="{BORDER_HOT}" stroke-opacity="0.35" stroke-width="1"/>'
    )
    # boot header
    out.append(
        f'<text x="34" y="44" font-size="13" fill="{AMBER}">MOHAFIZAAN-OS '
        f"<tspan fill=\"{DIM}\">v4.2.2010 // BIOS</tspan></text>"
    )
    out.append(
        f'<text x="{w-34}" y="44" font-size="12" fill="{FAINT}" text-anchor="end">'
        f"MEM OK · CRT 60HZ</text>"
    )
    out.append(
        f'<line x1="34" y1="54" x2="{w-34}" y2="54" stroke="{BORDER_HOT}" '
        f'stroke-opacity="0.25" stroke-width="1"/>'
    )
    # pixel name with glow
    out.append(
        f'<g filter="url(#glow)">{pixel_text(word, (w-pw)//2, 92, scale)}</g>'
    )
    # subtitle
    out.append(
        f'<text x="{w//2}" y="190" font-size="21" letter-spacing="4" fill="{BRIGHT}" '
        f'text-anchor="middle">ENTERPRISE APPLICATION MAGICIAN</text>'
    )
    # boot log
    logs = [
        "> LOADING PROFILE.SYS ......... OK",
        "> LOADING SKILLS.DAT .......... OK",
        "> ESTABLISHING UPLINK ......... 56K",
        "> READY.",
    ]
    y = 228
    for line in logs:
        out.append(
            f'<text x="34" y="{y}" font-size="14" fill="{DIM}">{line}</text>'
        )
        if line.endswith("READY."):
            cx = 34 + len(line) * 8.4 + 6
            out.append(f'<rect x="{cx:.0f}" y="{y-13}" width="10" height="14" fill="{AMBER}"/>')
        y += 24
    # footer meta
    out.append(
        f'<text x="34" y="{h-24}" font-size="11" fill="{FAINT}">'
        f"(C) 2010-2026 SKYJUICE LABS</text>"
    )
    out.append(
        f'<text x="{w-34}" y="{h-24}" font-size="11" fill="{FAINT}" text-anchor="end">'
        f"[ CRT OUTPUT // 800x340 ]</text>"
    )
    out.append(overlay(w, h))
    out.append("</svg>")
    return "\n".join(out)


# --- tech stack panel ---------------------------------------------------------------

TECHS = [
    ("TypeScript", 12, "production"),
    ("JavaScript", 11, "daily driver"),
    ("Node.js", 10, "server-side"),
    ("Python", 7, "data & glue"),
    ("React", 9, "ui layer"),
    ("Next.js", 8, "full-stack"),
    ("Tailwind", 9, "styling"),
    ("Docker", 6, "ship it"),
    ("PostgreSQL", 5, "storage"),
    ("Git", 8, "never leave home"),
]


def techs_panel() -> str:
    w, h = 800, 282
    out = [panel_open(w, h), DEFS]
    out.append(title(w, "> TECHS.SYS", 150))
    out.append(status_right(w, "[MODULES: 10]"))
    bar_x, bar_w, bar_h, gap, blocks = 190, 8, 12, 2, 40
    y = 56
    for name, level, status in TECHS:
        out.append(f'<text x="30" y="{y+13}" font-size="14" fill="{BRIGHT}">{name}</text>')
        for i in range(blocks):
            x = bar_x + i * (bar_w + gap)
            color = AMBER if i < level * 4 else TRACK
            out.append(
                f'<rect x="{x}" y="{y+1}" width="{bar_w}" height="{bar_h}" fill="{color}"/>'
            )
        out.append(
            f'<text x="704" y="{y+13}" font-size="12" fill="{DIM}">'
            f"// {esc(status)}</text>"
        )
        y += 22
    out.append(overlay(w, h))
    out.append("</svg>")
    return "\n".join(out)


# --- stats card ---------------------------------------------------------------------

def stats_card(u: dict) -> str:
    w, h = 500, 205
    since = datetime.now(timezone.utc) - datetime.fromisoformat(
        u["createdAt"].replace("Z", "+00:00")
    )
    repos = u["repositories"]["nodes"]
    cells = [
        ("TOTAL STARS", sum(r["stargazerCount"] for r in repos)),
        ("COMMITS", u["contributionsCollection"]["totalCommitContributions"]),
        ("PULL REQUESTS", u["contributionsCollection"]["totalPullRequestContributions"]),
        ("ISSUES", u["contributionsCollection"]["totalIssueContributions"]),
        ("PUBLIC REPOS", u["repositories"]["totalCount"]),
        ("FOLLOWERS", u["followers"]["totalCount"]),
        ("FOLLOWING", u["following"]["totalCount"]),
        ("YEARS ONLINE", math.floor(since.days / 365.25)),
    ]
    out = [panel_open(w, h), DEFS]
    out.append(
        f'<rect x="0" y="0" width="{w}" height="3" fill="url(#grad)"/>'
    )
    out.append(title(w, "> GITHUB.STATS", 168))
    out.append(status_right(w, f"[SINCE {datetime.fromisoformat(u['createdAt'].replace('Z','+00:00')).year}]"))
    cols, cell_w, cell_h = 4, (w - 40) // 4, 66
    for i, (label, value) in enumerate(cells):
        cx = 20 + (i % cols) * cell_w + cell_w / 2
        row_y = 62 + (i // cols) * cell_h
        out.append(
            f'<text x="{cx}" y="{row_y}" font-size="23" font-weight="700" '
            f'fill="{BRIGHT}" text-anchor="middle" filter="url(#glow)">{fmt_num(value)}</text>'
        )
        out.append(
            f'<text x="{cx}" y="{row_y+18}" font-size="9" letter-spacing="2" '
            f'fill="{DIM}" text-anchor="middle">{esc(label)}</text>'
        )
    out.append(overlay(w, h))
    out.append("</svg>")
    return "\n".join(out)


# --- top languages card ----------------------------------------------------------------

def langs_card(u: dict) -> str:
    w, h = 400, 215
    totals: dict = {}
    for r in u["repositories"]["nodes"]:
        if r["isFork"]:
            continue
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            color = e["node"]["color"] or "#8b949e"
            totals[name] = (totals.get(name, (0, color))[0] + e["size"], color)
    ranked = sorted(totals.items(), key=lambda kv: -kv[1][0])[:6]
    total = sum(v[1][0] for v in ranked) or 1

    out = [panel_open(w, h), DEFS]
    out.append(title(w, "> TOP.LANGS", 144))
    out.append(status_right(w, "[PUBLIC]"))
    row_h = 26
    for i, (name, (size, color)) in enumerate(ranked):
        y = 56 + i * row_h
        pct = size / total
        out.append(f'<circle cx="20" cy="{y-3}" r="4.5" fill="{color}"/>')
        out.append(f'<text x="32" y="{y+1}" font-size="12.5" fill="{BRIGHT}">{esc(name)}</text>')
        out.append(
            f'<text x="{w-20}" y="{y+1}" font-size="11.5" fill="{DIM}" '
            f'text-anchor="end">{pct*100:.1f}%</text>'
        )
        bar_w = (w - 40) * pct
        out.append(
            f'<rect x="20" y="{y+6}" width="{w-40}" height="6" fill="{TRACK}"/>'
        )
        out.append(
            f'<rect x="20" y="{y+6}" width="{bar_w:.1f}" height="6" fill="{color}"/>'
        )
    out.append(overlay(w, h))
    out.append("</svg>")
    return "\n".join(out)


# --- system info panel -----------------------------------------------------------------

def sysinfo_card(u: dict) -> str:
    w, h = 800, 152
    rows = [
        ("USER", (u["name"] or USER).lower()),
        ("COMPANY", (u["company"] or "—").lower()),
        ("LOCATION", (u["location"] or "—").lower()),
        ("WEB", (u["websiteUrl"] or "—").replace("https://", "")),
        ("MEMBER SINCE", u["createdAt"][:10]),
        ("MODE", "retro crt // amber phosphor"),
    ]
    out = [panel_open(w, h), DEFS]
    out.append(title(w, "> SYSTEM.INFO", 168))
    out.append(status_right(w, "[READ ONLY]"))
    col_x = [30, 420]
    for i, (key, val) in enumerate(rows):
        x = col_x[i % 2]
        y = 72 + (i // 2) * 30
        out.append(f'<text x="{x}" y="{y}" font-size="13" fill="{DIM}">{key} ....</text>')
        out.append(f'<text x="{x+118}" y="{y}" font-size="13" fill="{BRIGHT}">{esc(val)}</text>')
    out.append(overlay(w, h))
    out.append("</svg>")
    return "\n".join(out)


# --- project card ----------------------------------------------------------------------

def project_card(repo: dict) -> str:
    w, h = 390, 135
    name = repo["name"]
    desc = repo["description"] or FALLBACK_DESCRIPTIONS.get(name, "")
    lang = repo["primaryLanguage"]
    if not (lang and lang["name"]) and repo["languages"]["edges"]:
        lang = repo["languages"]["edges"][0]["node"]
    out = [panel_open(w, h), DEFS]
    out.append(f'<rect x="0" y="0" width="{w}" height="3" fill="url(#grad)"/>')
    out.append(
        f'<text x="20" y="34" font-size="16" font-weight="700" fill="{BRIGHT}" '
        f'filter="url(#glow)">{esc(name)}</text>'
    )
    cursor_x = 20 + len(name) * 9.6 + 10
    out.append(f'<rect x="{cursor_x:.0f}" y="21" width="8" height="13" fill="{AMBER}" opacity="0.8"/>')
    if repo.get("isFork"):
        out.append(
            f'<text x="{w-20}" y="32" font-size="10" fill="{DIM}" text-anchor="end">'
            f"[FORK]</text>"
        )
    y = 60
    for line in wrap(desc, 46):
        out.append(
            f'<text x="20" y="{y}" font-size="11.5" fill="{MUTED}">{esc(line)}</text>'
        )
        y += 17
    out.append(
        f'<text x="{w-20}" y="120" font-size="12" fill="{AMBER}" text-anchor="end">'
        f"* {fmt_num(repo['stargazerCount'])}</text>"
    )
    if lang and lang["name"]:
        lang_color = lang["color"] or AMBER
        out.append(f'<circle cx="20" cy="116" r="4.5" fill="{lang_color}"/>')
        out.append(
            f'<text x="32" y="120" font-size="12" fill="{MUTED}">{esc(lang["name"])}</text>'
        )
    out.append(overlay(w, h))
    out.append("</svg>")
    return "\n".join(out)


# --- contact buttons ----------------------------------------------------------------------

BUTTONS = [
    ("btn-github", "[ GITHUB ]"),
    ("btn-web", "[ FAIZAN.MY ]"),
    ("btn-linkedin", "[ LINKEDIN ]"),
    ("btn-email", "[ EMAIL ]"),
    ("btn-all", "[ VIEW ALL REPOS ]"),
]


def contact_button(text: str, w: int = 230) -> str:
    h = 40
    out = [panel_open(w, h), DEFS]
    out.append(
        f'<rect x="0" y="0" width="{w}" height="{h}" rx="6" fill="{PANEL}" '
        f'stroke="{BORDER_HOT}" stroke-opacity="0.5" stroke-width="1"/>'
    )
    out.append(
        f'<text x="{w//2}" y="26" font-size="14" font-weight="700" fill="{BRIGHT}" '
        f'text-anchor="middle" filter="url(#glow)">{esc(text)}</text>'
    )
    out.append(f'<rect x="{w-24}" y="15" width="7" height="12" fill="{AMBER}" opacity="0.6"/>')
    out.append(overlay(w, h))
    out.append("</svg>")
    return "\n".join(out)


# --- footer --------------------------------------------------------------------------------

def footer() -> str:
    w, h = 800, 130
    out = [panel_open(w, h, bezel=True), DEFS]
    out.append(
        f'<rect x="16" y="16" width="{w-32}" height="{h-32}" rx="8" fill="{SCREEN}" '
        f'stroke="{BORDER_HOT}" stroke-opacity="0.35" stroke-width="1"/>'
    )
    out.append(
        f'<text x="{w//2}" y="62" font-size="18" font-weight="700" fill="{BRIGHT}" '
        f'text-anchor="middle" filter="url(#glow)">THANKS FOR STOPPING BY</text>'
    )
    out.append(
        f'<text x="{w//2}" y="92" font-size="12" fill="{DIM}" text-anchor="middle">'
        f"&gt; SESSION CLOSED · NO CARRIER · (C) 2010-2026 SKYJUICE LABS</text>"
    )
    out.append(overlay(w, h))
    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    os.makedirs(ASSETS, exist_ok=True)
    user = graphql(get_token(), QUERY)

    static = {
        "banner.svg": banner(),
        "techs.svg": techs_panel(),
        "sysinfo.svg": sysinfo_card(user),
        "stats.svg": stats_card(user),
        "langs.svg": langs_card(user),
        "footer.svg": footer(),
    }
    for fname, content in static.items():
        with open(os.path.join(ASSETS, fname), "w") as f:
            f.write(content)

    widths = {"btn-all": 260}
    for fname, label in BUTTONS:
        with open(os.path.join(ASSETS, f"{fname}.svg"), "w") as f:
            f.write(contact_button(label, widths.get(fname, 230)))

    by_name = {r["name"]: r for r in user["repositories"]["nodes"]}
    for repo_name in ["dsh-open-ide", "dsh-model-picker", "deepseek-harness"]:
        if repo_name in by_name:
            with open(os.path.join(ASSETS, f"{repo_name}.svg"), "w") as f:
                f.write(project_card(by_name[repo_name]))
    print("panels generated:", sorted(os.listdir(ASSETS)))


if __name__ == "__main__":
    main()
