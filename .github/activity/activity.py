#Activity
#Z GitHub API (posledný rok) vyrobí dve karty v štýle terminálu:
#- assets/activity.svg  pavučina (Commits, Issues, Pull requests, Code review) + 8 údajov
#- assets/uptime.svg    52 týždňov ako pilulky (Uptime Kuma štýl), na výšku
#Text je prevedený na tvary (JetBrains Mono), takže vyzerá rovnako v každom prehliadači.
#Použitie: GITHUB_TOKEN=... python activity.py <username> <výstupný priečinok>
import json
import math
import os
import sys
import urllib.request

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = {
    "regular": os.path.join(HERE, "fonts", "JetBrainsMono-Regular.woff"),
    "bold": os.path.join(HERE, "fonts", "JetBrainsMono-Bold.woff"),
}

#Farby (tyrkysová téma)
ACCENT = "#22d3ee"
ACCENT_LIGHT = "#67e8f9"
ACCENT_MID = "#0891b2"
ACCENT_DARK = "#155e75"
BG = "#0b0f14"
BAR = "#11161d"
MUTED = "#6e7681"
COMMAND = "#9aa4ae"
EMPTY = "#1c2128"

TITLE_PREFIX = "milan@github: "

QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER) { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


#GitHub API
def fetch(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "profile-activity"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(f"GitHub API: {data['errors']}")
    return data["data"]["user"]


def summarize(user):
    cc = user["contributionsCollection"]
    days = [d for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    days.sort(key=lambda d: d["date"])
    counts = [d["contributionCount"] for d in days]

    #Najdlhšia séria dní s aspoň jedným príspevkom
    best = run = 0
    for c in counts:
        run = run + 1 if c else 0
        best = max(best, run)
    #Aktuálna séria (dnešok bez príspevku ešte sériu nepreruší)
    current = 0
    tail = counts[:-1] if counts and counts[-1] == 0 else counts
    for c in reversed(tail):
        if not c:
            break
        current += 1

    #52 týždňov (posledný môže byť neúplný)
    weeks = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in cc["contributionCalendar"]["weeks"]][-52:]
    weeks = [0] * (52 - len(weeks)) + weeks

    return {
        "contributions": cc["contributionCalendar"]["totalContributions"],
        "commits": cc["totalCommitContributions"],
        "issues": cc["totalIssueContributions"],
        "pulls": cc["totalPullRequestContributions"],
        "reviews": cc["totalPullRequestReviewContributions"],
        "repositories": user["repositories"]["totalCount"],
        "best": best,
        "current": current,
        "weeks": weeks,
    }


#Text → tvary
_fonts = {}


def text(font, s, size, x, y, anchor="start"):
    if font not in _fonts:
        _fonts[font] = TTFont(FONTS[font])
    f = _fonts[font]
    glyphs = f.getGlyphSet()
    cmap = f.getBestCmap()
    k = size / f["head"].unitsPerEm
    names = [cmap.get(ord(ch), cmap[ord("?")]) for ch in s]
    width = sum(glyphs[n].width * k for n in names)
    if anchor == "middle":
        x -= width / 2
    elif anchor == "end":
        x -= width
    pen = SVGPathPen(glyphs)
    for n in names:
        glyphs[n].draw(TransformPen(pen, (k, 0, 0, -k, x, y)))
        x += glyphs[n].width * k
    return pen.getCommands(), width


def path(d, fill):
    return f'<path d="{d}" fill="{fill}"/>'


def window(width, height, title, command, inner, radius=14, small=False):
    dot_r, dot_gap, title_size, cmd_size, cmd_x, cmd_y = (5, 17, 14, 15, 24, 66) if small else (5.5, 18, 13, 15, 22, 64)
    t, _ = text("regular", title, title_size, width / 2 + (20 if small else 0), 25, "middle")
    d, dw = text("regular", "$ ", cmd_size, cmd_x, cmd_y)
    c, _ = text("regular", command, cmd_size, cmd_x + dw, cmd_y)
    dots = "".join(f'<circle cx="{20 + i * dot_gap}" cy="20" r="{dot_r}" fill="{col}"/>' for i, col in enumerate(["#ff5f57", "#febc2e", "#28c840"]))
    r = radius
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<rect width="{width}" height="{height}" rx="{r}" fill="{BG}"/>'
        f'<path d="M{r} 0H{width - r}A{r} {r} 0 0 1 {width} {r}V40H0V{r}A{r} {r} 0 0 1 {r} 0Z" fill="{BAR}"/>'
        f'<line x1="0" y1="40" x2="{width}" y2="40" stroke="#fff" stroke-opacity=".06"/>{dots}'
        f"{path(t, MUTED)}{path(d, ACCENT)}{path(c, COMMAND)}{inner}"
        f'<rect x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="{r}" fill="none" stroke="#fff" stroke-opacity=".08"/></svg>'
    )


def plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


#Activity
def render_activity(s):
    total = s["commits"] + s["issues"] + s["pulls"] + s["reviews"]
    pct = {k: (round(s[k] / total * 100) if total else 0) for k in ("commits", "issues", "pulls", "reviews")}
    cx, cy, R = 150, 212, 76
    axes = [("Code review", "reviews", 0, -1), ("Issues", "issues", 1, 0), ("Pull requests", "pulls", 0, 1), ("Commits", "commits", -1, 0)]
    g = ""
    for k in (0.25, 0.5, 0.75, 1):
        pts = " ".join(f"{cx + dx * R * k:.1f},{cy + dy * R * k:.1f}" for _, _, dx, dy in axes)
        g += f'<polygon points="{pts}" fill="none" stroke="#fff" stroke-opacity="{0.05 if k < 1 else 0.1}"/>'
    for _, _, dx, dy in axes:
        g += f'<line x1="{cx}" y1="{cy}" x2="{cx + dx * R}" y2="{cy + dy * R}" stroke="#fff" stroke-opacity=".08"/>'
    #Odmocnina, aby boli vidieť aj malé hodnoty (1 %, 4 %)
    scale = lambda v: max(0.06, math.sqrt(v / 100))
    pts = [(cx + dx * R * scale(pct[key]), cy + dy * R * scale(pct[key])) for _, key, dx, dy in axes]
    ps = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    g += '<defs><filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="5"/></filter></defs>'
    g += f'<polygon points="{ps}" fill="{ACCENT}" opacity=".35" filter="url(#glow)"/>'
    g += f'<polygon points="{ps}" fill="{ACCENT}" fill-opacity=".18" stroke="{ACCENT}" stroke-width="2" stroke-linejoin="round"/>'
    g += "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{BG}" stroke="{ACCENT_LIGHT}" stroke-width="2"/>' for x, y in pts)
    for label, key, dx, dy in axes:
        lx, ly = cx + dx * (R + 12), cy + dy * (R + 14)
        anchor = "middle" if dx == 0 else ("start" if dx > 0 else "end")
        if dy < 0:
            ly -= 20
        if dy > 0:
            ly += 12
        if dx:
            ly -= 8
        p1, _ = text("bold", f"{pct[key]}%", 14, lx, ly, anchor)
        p2, _ = text("regular", label, 11, lx, ly + 15, anchor)
        g += path(p1, ACCENT_LIGHT) + path(p2, MUTED)
    g += '<line x1="300" y1="104" x2="300" y2="318" stroke="#fff" stroke-opacity=".06"/>'
    rows = [
        (str(s["contributions"]), "contributions"),
        (str(s["commits"]), "commits"),
        (str(s["issues"]), "issues opened"),
        (str(s["pulls"]), "pull requests"),
        (str(s["reviews"]), "code reviews"),
        (str(s["repositories"]), "repositories"),
        (plural(s["best"], "day", "days"), "best streak"),
        (plural(s["current"], "day", "days"), "current streak"),
    ]
    for i, (value, label) in enumerate(rows):
        col, row = i % 4, i // 4
        x, y = 326 + col * 136, 162 + row * 92
        a, _ = text("bold", value, 22, x + 16, y + 4)
        b, _ = text("regular", label, 12, x + 16, y + 25)
        g += f'<rect x="{x}" y="{y - 10}" width="6" height="6" rx="1" fill="{ACCENT}"/>' + path(a, ACCENT_LIGHT) + path(b, MUTED)
    return window(880, 340, TITLE_PREFIX + "~/activity", "gh activity --year", g)


#Uptime
def level(w):
    if w == 0:
        return EMPTY
    if w <= 2:
        return ACCENT_DARK
    if w <= 5:
        return ACCENT_MID
    if w <= 9:
        return ACCENT
    return ACCENT_LIGHT


def render_uptime(s):
    weeks = s["weeks"]
    active = sum(1 for w in weeks if w)
    W, bw, bh, gx, gy, top = 240, 10, 40, 4.6, 15, 112
    x0 = (W - (13 * bw + 12 * gx)) / 2
    g = ""
    #4 riadky po 13 týždňov, zľava doprava a zhora dole: najstarší → najnovší
    for i, w in enumerate(weeks):
        r, c = i // 13, i % 13
        g += f'<rect x="{x0 + c * (bw + gx):.1f}" y="{top + r * (bh + gy)}" width="{bw}" height="{bh}" rx="2.5" fill="{level(w)}"/>'
    yb = top + 4 * bh + 3 * gy
    n1, _ = text("regular", "52 weeks ago", 14, x0, top - 12)
    n2, _ = text("regular", "now", 14, W - x0, yb + 22, "end")
    p1, _ = text("bold", f"{round(active / 52 * 100)}%", 30, x0, yb + 64)
    p2, _ = text("regular", "active weeks", 14, x0, yb + 88)
    p3, _ = text("regular", f"{active} of 52", 14, x0, yb + 107)
    g += path(n1, MUTED) + path(n2, MUTED) + path(p1, ACCENT_LIGHT) + path(p2, MUTED) + path(p3, MUTED)
    return window(W, yb + 22 + 98, "~/uptime", "uptime", g, radius=12, small=True)


def main():
    login, out_dir = sys.argv[1], sys.argv[2]
    s = summarize(fetch(login, os.environ["GITHUB_TOKEN"]))
    os.makedirs(out_dir, exist_ok=True)
    for name, svg in (("activity.svg", render_activity(s)), ("uptime.svg", render_uptime(s))):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            f.write(svg)
    print("Activity:", json.dumps({k: v for k, v in s.items() if k != "weeks"}))
    print("Uptime:", sum(1 for w in s["weeks"] if w), "of 52 weeks active")


if __name__ == "__main__":
    main()
