#!/usr/bin/env python3
"""Discover agent-first CLI tools from GitHub and open an Issue with candidates."""

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GITHUB_API = "https://api.github.com"
OWNER_REPO = "RealZST/harnesskit-resources"  # where issues are created
LABEL = "cli-discovery"
MAX_CANDIDATES_IN_ISSUE = 20
SEARCH_PER_QUERY = 30  # max results per search query
SEARCH_DELAY = 2  # seconds between search queries (rate-limit guard)

INSTALL_KEYWORDS = [
    "npm install -g",
    "pip install",
    "go install",
    "brew install",
    "cargo install",
    "curl | sh",
    "curl -fsSL",
]

AGENT_KEYWORDS = [
    "agent",
    "ai-native",
    "llm",
    "claude",
    "cursor",
    "codex",
    "coding assistant",
    "aider",
    "copilot",
    "non-interactive",
    "structured output",
    "agent-first",
    "agent-native",
]

SEARCH_QUERIES = [
    '"agent cli" in:readme,description',
    '"agent-first" in:readme,description',
    '"agent-native" in:readme,description',
    '"Claude" cli in:readme,description',
    '"Cursor" cli in:readme,description',
    '"Codex" cli in:readme,description',
    '"LLM" cli in:readme,description',
    '"coding assistant" cli in:readme,description',
    "topic:agent-cli",
    "topic:ai-cli",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
}


def gh_get(url: str, *, raw: bool = False, params: dict | None = None):
    """GET a GitHub API URL. Returns parsed JSON or raw text."""
    headers = dict(HEADERS)
    if raw:
        headers["Accept"] = "application/vnd.github.raw"
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    if raw:
        resp.raise_for_status()
        return resp.text
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def gh_post(url: str, payload: dict):
    resp = requests.post(url, headers=HEADERS, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def gh_put(url: str, payload: dict):
    resp = requests.put(url, headers=HEADERS, json=payload, timeout=30)
    # 422 = already exists — that's fine for label creation
    if resp.status_code == 422:
        return None
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Step 1: Load exclusion set from registry.json
# ---------------------------------------------------------------------------


def load_exclusion_set() -> set[str]:
    registry_path = Path(__file__).resolve().parent.parent.parent / "cli-registry" / "registry.json"
    print(f"Loading registry from {registry_path}")
    try:
        with open(registry_path) as f:
            registry = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"Warning: could not load registry ({exc}), using empty exclusion set")
        return set()
    excluded = {entry["skills_repo"].lower() for entry in registry if entry.get("skills_repo")}
    print(f"Exclusion set ({len(excluded)} repos): {excluded}")
    return excluded


# ---------------------------------------------------------------------------
# Step 2: Search GitHub for candidate repos
# ---------------------------------------------------------------------------


def search_candidates() -> dict[str, dict]:
    """Run all search queries and merge results by full_name."""
    candidates: dict[str, dict] = {}

    for query in SEARCH_QUERIES:
        print(f"\nSearch: {query}")
        try:
            data = gh_get(
                f"{GITHUB_API}/search/repositories",
                params={"q": query, "per_page": SEARCH_PER_QUERY, "sort": "stars", "order": "desc"},
            )
            if data is None:
                print("  -> no results (404)")
                continue
            items = data.get("items", [])
            print(f"  -> {len(items)} results (total_count={data.get('total_count', '?')})")
            for repo in items:
                full_name = repo["full_name"]
                if full_name not in candidates:
                    candidates[full_name] = repo
        except Exception as exc:
            print(f"  -> ERROR: {exc}")

        time.sleep(SEARCH_DELAY)

    print(f"\nTotal unique candidates after search: {len(candidates)}")
    return candidates


# ---------------------------------------------------------------------------
# Step 3: Filtering & scoring
# ---------------------------------------------------------------------------


def fetch_readme(full_name: str) -> str | None:
    """Fetch raw README content for a repo."""
    try:
        return gh_get(f"{GITHUB_API}/repos/{full_name}/readme", raw=True)
    except Exception:
        return None


def has_install_command(readme: str) -> bool:
    readme_lower = readme.lower()
    return any(kw.lower() in readme_lower for kw in INSTALL_KEYWORDS)


def has_agent_keywords(readme: str, description: str) -> bool:
    combined = (readme + " " + (description or "")).lower()
    return any(kw.lower() in combined for kw in AGENT_KEYWORDS)


def detect_install_command(readme: str) -> str:
    """Try to extract an actual install command from the README."""
    for kw in INSTALL_KEYWORDS:
        idx = readme.lower().find(kw.lower())
        if idx != -1:
            # grab the line containing the keyword
            start = readme.rfind("\n", 0, idx)
            end = readme.find("\n", idx)
            line = readme[start + 1 : end if end != -1 else len(readme)].strip()
            # strip markdown backticks
            line = line.strip("`").strip()
            if line:
                return line
    return "not detected"


def file_exists(full_name: str, path: str) -> bool:
    """Check if a file/directory exists in a repo."""
    try:
        resp = requests.get(
            f"{GITHUB_API}/repos/{full_name}/contents/{path}",
            headers=HEADERS,
            timeout=15,
        )
        return resp.status_code == 200
    except Exception:
        return False


BINARY_INDICATORS = ("linux", "darwin", "macos", "windows", "amd64", "x86_64", "arm64", "aarch64",
                      ".exe", ".deb", ".rpm", ".msi", ".appimage", ".dmg")


def has_binary_release(full_name: str) -> bool:
    """Check if the latest release has prebuilt binary assets."""
    try:
        data = gh_get(f"{GITHUB_API}/repos/{full_name}/releases/latest")
        if data is None:
            return False
        assets = data.get("assets", [])
        for asset in assets:
            name = asset.get("name", "").lower()
            # Look for platform-specific asset names that indicate prebuilt binaries
            if any(ind in name for ind in BINARY_INDICATORS):
                return True
    except Exception:
        pass
    return False


def extract_readme_excerpt(readme: str) -> str:
    """Extract up to 200 chars of README around agent-first keywords."""
    readme_lower = readme.lower()
    for kw in AGENT_KEYWORDS:
        idx = readme_lower.find(kw.lower())
        if idx != -1:
            # take a window around the match
            start = max(0, idx - 60)
            end = min(len(readme), idx + 140)
            excerpt = readme[start:end].replace("\n", " ").strip()
            if start > 0:
                excerpt = "..." + excerpt
            if end < len(readme):
                excerpt = excerpt + "..."
            return excerpt
    return readme[:200].replace("\n", " ").strip()


def score_candidate(full_name: str, repo: dict, readme: str) -> tuple[int, list[str]]:
    """Calculate score and return (score, list_of_signals)."""
    score = 0
    signals: list[str] = []

    # SKILL.md or .skill/ directory
    if file_exists(full_name, "SKILL.md") or file_exists(full_name, ".skill"):
        score += 3
        signals.append("SKILL.md / .skill/ (+3)")

    # MCP files
    if file_exists(full_name, "mcp.json") or file_exists(full_name, ".mcp.json"):
        score += 2
        signals.append("MCP files (+2)")

    # Stars
    stars = repo.get("stargazers_count", 0)
    if stars > 100:
        score += 3
        signals.append(f"stars > 100 (+3)")
    elif stars >= 50:
        score += 2
        signals.append(f"stars 50-100 (+2)")
    elif stars >= 10:
        score += 1
        signals.append(f"stars 10-50 (+1)")

    # Recent activity
    pushed_at = repo.get("pushed_at", "")
    if pushed_at:
        try:
            pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
            if pushed > datetime.now(timezone.utc) - timedelta(days=180):
                score += 2
                signals.append("active within 6 months (+2)")
        except Exception:
            pass

    # Structured output
    readme_lower = readme.lower()
    if "--json" in readme_lower or "--output" in readme_lower:
        score += 1
        signals.append("structured output (--json/--output) (+1)")

    # Prebuilt binaries
    if has_binary_release(full_name):
        score += 2
        signals.append("prebuilt binaries (+2)")

    return score, signals


def filter_and_score(candidates: dict[str, dict], exclusion: set[str]) -> list[dict]:
    """Apply must-have filters, exclusion rules, and scoring."""
    results: list[dict] = []

    for full_name, repo in candidates.items():
        print(f"\nChecking {full_name} ...")

        # Exclusion: already in registry
        if full_name.lower() in exclusion:
            print(f"  SKIP: already in registry")
            continue

        # Exclusion: stars < 3
        stars = repo.get("stargazers_count", 0)
        if stars < 3:
            print(f"  SKIP: stars={stars} < 3")
            continue

        # Exclusion: archived
        if repo.get("archived", False):
            print(f"  SKIP: archived")
            continue

        # Exclusion: fork
        if repo.get("fork", False):
            print(f"  SKIP: fork")
            continue

        # Must-have: has README & repo size > 0
        if repo.get("size", 0) == 0:
            print(f"  SKIP: repo size is 0")
            continue

        # Fetch README
        try:
            readme = fetch_readme(full_name)
        except Exception as exc:
            print(f"  SKIP: failed to fetch README ({exc})")
            continue

        if not readme:
            print(f"  SKIP: no README")
            continue

        # Must-have: install command keywords
        if not has_install_command(readme):
            print(f"  SKIP: no install command found in README")
            continue

        # Must-have: agent-first keywords
        description = repo.get("description", "") or ""
        if not has_agent_keywords(readme, description):
            print(f"  SKIP: no agent-first keywords")
            continue

        # Passed all must-haves — now score
        try:
            score, signals = score_candidate(full_name, repo, readme)
        except Exception as exc:
            print(f"  ERROR scoring: {exc}, using score=0")
            score, signals = 0, []

        install_cmd = detect_install_command(readme)
        excerpt = extract_readme_excerpt(readme)

        result = {
            "full_name": full_name,
            "display_name": repo.get("name", full_name.split("/")[-1]),
            "description": description,
            "stars": stars,
            "score": score,
            "signals": signals,
            "install_command": install_cmd,
            "readme_excerpt": excerpt,
            "html_url": repo.get("html_url", f"https://github.com/{full_name}"),
        }
        results.append(result)
        print(f"  PASS: score={score}, signals={signals}")

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:MAX_CANDIDATES_IN_ISSUE]


# ---------------------------------------------------------------------------
# Step 4: Create GitHub Issue
# ---------------------------------------------------------------------------


def ensure_label():
    """Create the cli-discovery label if it doesn't exist."""
    print(f"\nEnsuring label '{LABEL}' exists...")
    try:
        resp = requests.post(
            f"{GITHUB_API}/repos/{OWNER_REPO}/labels",
            headers=HEADERS,
            json={"name": LABEL, "color": "0e8a16", "description": "Auto-discovered CLI candidates"},
            timeout=15,
        )
        if resp.status_code == 422:
            print(f"  Label '{LABEL}' already exists")
        elif resp.status_code >= 400:
            print(f"  Warning: label creation returned {resp.status_code}: {resp.text}")
        else:
            print(f"  Label '{LABEL}' created")
    except Exception as exc:
        print(f"  Warning: failed to create label ({exc})")


def create_issue(candidates: list[dict]):
    """Create a GitHub Issue with the discovery results."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    n = len(candidates)
    title = f"\U0001f50d CLI Discovery: {today} \u2014 {n} candidates found"

    body_parts = [
        "## Agent-first CLI Candidates\n",
        f"Auto-discovered on {today}. Review each candidate and check the ones to add to `registry.json`.\n",
        "### Candidates\n",
    ]

    for i, c in enumerate(candidates, 1):
        signals_str = ", ".join(c["signals"]) if c["signals"] else "none"
        body_parts.append(
            f"#### {i}. {c['display_name']} \u2014 \u2b50 {c['stars']} \u2014 Score: {c['score']}\n"
            f"- **Repo**: [{c['full_name']}]({c['html_url']})\n"
            f"- **Description**: {c['description']}\n"
            f"- **Install**: `{c['install_command']}`\n"
            f"- **Signals**: {signals_str}\n"
            f"- **README excerpt**: {c['readme_excerpt']}\n"
        )

    body_parts.append("---\n")
    body_parts.append(
        "### Screening criteria\n"
        "- Must-have: CLI tool + agent-first design + open source + usable\n"
        "- Scored by: SKILL.md (+3), MCP files (+2), stars, recent activity, structured output, prebuilt binaries\n"
    )
    body_parts.append("\n\U0001f916 Auto-generated by [discover-cli workflow]\n")

    body = "\n".join(body_parts)

    ensure_label()

    print(f"\nCreating issue: {title}")
    issue = gh_post(
        f"{GITHUB_API}/repos/{OWNER_REPO}/issues",
        {"title": title, "body": body, "labels": [LABEL]},
    )
    print(f"Issue created: {issue.get('html_url', '(unknown URL)')}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    if not TOKEN:
        print("ERROR: GITHUB_TOKEN environment variable is not set.")
        raise SystemExit(1)

    print("=" * 60)
    print("CLI Discovery Script")
    print("=" * 60)

    # Step 1
    exclusion = load_exclusion_set()

    # Step 2
    candidates = search_candidates()

    # Step 3
    results = filter_and_score(candidates, exclusion)

    # Step 4
    if results:
        print(f"\n{'=' * 60}")
        print(f"Found {len(results)} candidates. Creating issue...")
        create_issue(results)
    else:
        print(f"\n{'=' * 60}")
        print("No new candidates found. No issue will be created.")

    print("\nDone.")


if __name__ == "__main__":
    main()
