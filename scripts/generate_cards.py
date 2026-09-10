#!/usr/bin/env python3
"""Generate profile stat cards (SVG) for the skyjuice GitHub profile README.

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

# --- theme (radical-inspired) -------------------------------------------------
BG = "#141321"
BORDER = "#30363d"
TITLE = "#fe428e"
LABEL = "#9f4bff"
TEXT = "#ffffff"
MUTED = "#9f9f9f"
TRACK = "#2d2b3a"
GRAD_A = "#fe428e"
GRAD_B = "#9f4bff"
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"

FALLBACK_DESCRIPTIONS = {
    "dsh-open-ide": "Open a DeepSeek Harness session in your IDE or file manager — one-command dsh bundle plugin",
    "dsh-model-picker": "Enhanced model picker for DeepSeek Harness — favourites, search, free/paid pricing",
    "deepseek-harness": "DeepSeek Harness: Everything is a Plugin.",
}

QUERY = """
query {
  user(login: "%s") {
    createdAt
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


# --- helpers ------------------------------------------------------------------

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


def gradient_top(width: int) -> str:
    return (
        f'<defs><linearGradient id="grad" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0%" stop-color="{GRAD_A}"/>'
        f'<stop offset="100%" stop-color="{GRAD_B}"/>'
        f"</linearGradient></defs>"
        f'<rect x="0" y="0" width="{width}" height="4" rx="2" fill="url(#grad)"/>'
    )


def card_open(w: int, h: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" font-family="{FONT}">'
        f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="10" fill="{BG}" '
        f'stroke="{BORDER}" stroke-width="1"/>'
    )


# --- card 1: stats -------------------------------------------------------------

def stats_card(u: dict) -> str:
    w, h = 500, 205
    since = datetime.now(timezone.utc) - datetime.fromisoformat(
        u["createdAt"].replace("Z", "+00:00")
    )
    repos = u["repositories"]["nodes"]
    cells = [
        ("Total Stars", sum(r["stargazerCount"] for r in repos)),
        ("Total Commits", u["contributionsCollection"]["totalCommitContributions"]),
        ("Pull Requests", u["contributionsCollection"]["totalPullRequestContributions"]),
        ("Issues", u["contributionsCollection"]["totalIssueContributions"]),
        ("Public Repos", u["repositories"]["totalCount"]),
        ("Followers", u["followers"]["totalCount"]),
        ("Following", u["following"]["totalCount"]),
        ("Years on GitHub", math.floor(since.days / 365.25)),
    ]
    out = [card_open(w, h), gradient_top(w)]
    out.append(
        f'<text x="20" y="38" font-size="17" font-weight="700" fill="{TITLE}">'
        f"{esc(USER)}&#39;s GitHub Stats</text>"
    )
    out.append(
        f'<text x="{w-20}" y="38" font-size="11" fill="{LABEL}" text-anchor="end">'
        f"since {datetime.fromisoformat(u['createdAt'].replace('Z','+00:00')).year}</text>"
    )
    cols, cell_w, cell_h = 4, (w - 40) // 4, 66
    for i, (label, value) in enumerate(cells):
        cx = 20 + (i % cols) * cell_w + cell_w / 2
        row_y = 66 + (i // cols) * cell_h
        out.append(
            f'<text x="{cx}" y="{row_y}" font-size="24" font-weight="700" '
            f'fill="{TEXT}" text-anchor="middle">{fmt_num(value)}</text>'
        )
        out.append(
            f'<text x="{cx}" y="{row_y+20}" font-size="10" letter-spacing="1" '
            f'fill="{LABEL}" text-anchor="middle">{esc(label.upper())}</text>'
        )
    out.append("</svg>")
    return "\n".join(out)


# --- card 2: top languages -----------------------------------------------------

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

    out = [card_open(w, h), gradient_top(w)]
    out.append(
        f'<text x="20" y="38" font-size="17" font-weight="700" fill="{TITLE}">'
        f"Top Languages</text>"
    )
    out.append(
        f'<text x="{w-20}" y="38" font-size="11" fill="{LABEL}" text-anchor="end">'
        f"public repos</text>"
    )
    row_h = 26
    for i, (name, (size, color)) in enumerate(ranked):
        y = 60 + i * row_h
        pct = size / total
        out.append(f'<circle cx="20" cy="{y-4}" r="5" fill="{color}"/>')
        out.append(
            f'<text x="34" y="{y}" font-size="13" fill="{TEXT}">{esc(name)}</text>'
        )
        out.append(
            f'<text x="{w-20}" y="{y}" font-size="12" fill="{LABEL}" '
            f'text-anchor="end">{pct*100:.1f}%</text>'
        )
        bar_w = (w - 40) * pct
        out.append(
            f'<rect x="20" y="{y+5}" width="{w-40}" height="6" rx="3" fill="{TRACK}"/>'
        )
        out.append(
            f'<rect x="20" y="{y+5}" width="{bar_w:.1f}" height="6" rx="3" fill="{color}"/>'
        )
    out.append("</svg>")
    return "\n".join(out)


# --- card 3: project ------------------------------------------------------------

def project_card(repo: dict) -> str:
    w, h = 390, 135
    name = repo["name"]
    desc = repo["description"] or FALLBACK_DESCRIPTIONS.get(name, "")
    lang = repo["primaryLanguage"]
    if not (lang and lang["name"]) and repo["languages"]["edges"]:
        lang = repo["languages"]["edges"][0]["node"]
    out = [card_open(w, h), gradient_top(w)]
    out.append(
        f'<text x="20" y="34" font-size="17" font-weight="700" fill="{TEXT}">'
        f"{esc(name)}</text>"
    )
    if repo.get("isFork"):
        out.append(
            f'<text x="{w-20}" y="32" font-size="10" fill="{LABEL}" text-anchor="end">'
            f"fork</text>"
        )
    y = 60
    for line in wrap(desc, 48):
        out.append(
            f'<text x="20" y="{y}" font-size="12" fill="{MUTED}">{esc(line)}</text>'
        )
        y += 17
    star_x = w - 20
    out.append(
        f'<text x="{star_x}" y="120" font-size="12" fill="{LABEL}" text-anchor="end">'
        f"★ {fmt_num(repo['stargazerCount'])}</text>"
    )
    if lang and lang["name"]:
        lang_color = lang["color"] or LABEL
        out.append(f'<circle cx="20" cy="116" r="5" fill="{lang_color}"/>')
        out.append(
            f'<text x="32" y="120" font-size="12" fill="{LABEL}">{esc(lang["name"])}</text>'
        )
    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    os.makedirs(ASSETS, exist_ok=True)
    user = graphql(get_token(), QUERY)
    with open(os.path.join(ASSETS, "stats.svg"), "w") as f:
        f.write(stats_card(user))
    with open(os.path.join(ASSETS, "langs.svg"), "w") as f:
        f.write(langs_card(user))
    by_name = {r["name"]: r for r in user["repositories"]["nodes"]}
    for repo_name in ["dsh-open-ide", "dsh-model-picker", "deepseek-harness"]:
        if repo_name in by_name:
            with open(os.path.join(ASSETS, f"{repo_name}.svg"), "w") as f:
                f.write(project_card(by_name[repo_name]))
    print("cards generated:", os.listdir(ASSETS))


if __name__ == "__main__":
    main()
