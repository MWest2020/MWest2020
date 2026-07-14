#!/usr/bin/env python3
"""Refresh the 'Selected work' section of the profile README.

Ranks the owner's public repos by commit count over the last 30 days
(tiebreak: most recent push) and rewrites the list between the
selected-work markers. Stdlib only; GITHUB_TOKEN is optional but
avoids rate limits.
"""
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

OWNER = "MWest2020"
# Already featured elsewhere on the profile, or not a project.
EXCLUDE = {"MWest2020", "handbook", "westerweel-work"}
README = os.path.join(os.path.dirname(__file__), "..", "README.md")
START = "<!-- selected-work:start -->"
END = "<!-- selected-work:end -->"
TOP_N = 6
CANDIDATES = 15
WINDOW_DAYS = 30


def api(path):
    req = urllib.request.Request("https://api.github.com" + path)
    req.add_header("Accept", "application/vnd.github+json")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        if e.code in (404, 409):  # 409 = empty repository
            return []
        raise


def main():
    repos, page = [], 1
    while True:
        batch = api(f"/users/{OWNER}/repos?type=owner&sort=pushed&per_page=100&page={page}")
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    repos = [
        r for r in repos
        if not r["fork"] and not r["archived"] and not r["private"]
        and r["name"] not in EXCLUDE
    ][:CANDIDATES]  # listing is sorted by pushed_at

    since = (datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ranked = []
    for r in repos:
        commits = api(f"/repos/{OWNER}/{r['name']}/commits?since={since}&per_page=100")
        ranked.append((len(commits), r["pushed_at"], r))
    ranked.sort(key=lambda t: (t[0], t[1]), reverse=True)

    top = [t for t in ranked if t[0] > 0][:TOP_N]
    if len(top) < TOP_N:  # pad with most recently pushed
        seen = {t[2]["name"] for t in top}
        top += [t for t in ranked if t[2]["name"] not in seen][:TOP_N - len(top)]

    lines = []
    for _, _, r in top:
        desc = (r["description"] or "").strip().rstrip(".")
        line = f"- **[{r['name']}]({r['html_url']})**"
        if desc:
            line += f" — {desc}."
        lines.append(line)
    block = "\n".join([START] + lines + [END])

    with open(README, encoding="utf-8") as f:
        text = f.read()
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), block, text, flags=re.S)
    if new == text:
        print("no changes")
        return
    with open(README, "w", encoding="utf-8") as f:
        f.write(new)
    print("updated: " + ", ".join(t[2]["name"] for t in top))


if __name__ == "__main__":
    main()
