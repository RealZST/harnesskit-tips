#!/usr/bin/env python3
"""Discover tips from official documentation and open an Issue with candidates."""

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GITHUB_API = "https://api.github.com"
OWNER_REPO = "RealZST/harnesskit-resources"
LABEL = "tips-discovery"
MAX_CANDIDATES_IN_ISSUE = 40
SEARCH_DELAY = 1  # seconds between requests (rate-limit guard)

# Signals that a sentence is an actionable tip
ACTION_VERBS = re.compile(
    r"\b(Use|Run|Type|Press|Add|Set|Put|Create|Open|Start|Enable|Disable|Configure|Toggle|Prefix|Save|Define|Override|Pick)\b"
)

# Patterns that indicate useful content
TIP_SIGNALS = [
    re.compile(r"[/@#!]\w"),                     # command syntax: /foo, @bar, #baz, !cmd
    re.compile(r"(Cmd|Ctrl|Alt|Shift)\s*[+]"),   # keyboard shortcuts
    re.compile(r"--\w{2,}"),                      # CLI flags: --json, --style
    re.compile(r"-[a-zA-Z]\b"),                   # short flags: -p, -c
    re.compile(r"\.\w+\.json|\.\w+\.md|\.\w+\.toml"),  # file paths
    re.compile(r"`[^`]{3,60}`"),                  # inline code (3-60 chars)
]

# Minimum signals required for a sentence to be a candidate
MIN_SIGNALS = 2

TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github+json",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def gh_get(url: str, *, raw: bool = False, params: dict | None = None):
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


def fetch_url(url: str) -> str | None:
    """Fetch a URL and return text content."""
    try:
        resp = requests.get(url, timeout=30, headers={"User-Agent": "HarnessKit-TipsBot/1.0"})
        if resp.status_code == 200:
            return resp.text
    except Exception as exc:
        print(f"  Warning: failed to fetch {url} ({exc})")
    return None


# ---------------------------------------------------------------------------
# Step 1: Load existing tips for deduplication
# ---------------------------------------------------------------------------


def load_existing_tips() -> set[str]:
    """Load existing tip texts as a set of lowercased keyword bags for fuzzy dedup."""
    tips_path = Path(__file__).resolve().parent.parent.parent / "tips" / "tips.json"
    existing: set[str] = set()
    try:
        with open(tips_path) as f:
            tips = json.load(f)
        for tip in tips:
            # Store normalized keywords for comparison
            existing.add(normalize_for_dedup(tip["tip"]))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"Warning: could not load existing tips ({exc})")
    print(f"Loaded {len(existing)} existing tips for dedup")
    return existing


def normalize_for_dedup(text: str) -> str:
    """Extract keywords from text for fuzzy matching."""
    # Remove punctuation, lowercase, extract words 3+ chars
    words = re.findall(r"[a-zA-Z_/\-@#!]{3,}", text.lower())
    return " ".join(sorted(set(words)))


def is_duplicate(candidate: str, existing: set[str], threshold: float = 0.6) -> bool:
    """Check if a candidate tip is too similar to any existing tip."""
    candidate_norm = normalize_for_dedup(candidate)
    candidate_words = set(candidate_norm.split())
    if not candidate_words:
        return True
    for existing_norm in existing:
        existing_words = set(existing_norm.split())
        if not existing_words:
            continue
        overlap = len(candidate_words & existing_words)
        similarity = overlap / min(len(candidate_words), len(existing_words))
        if similarity >= threshold:
            return True
    return False


# ---------------------------------------------------------------------------
# Step 2: Fetch content from sources
# ---------------------------------------------------------------------------


def load_sources() -> list[dict]:
    sources_path = Path(__file__).resolve().parent.parent.parent / "tips" / "sources.json"
    with open(sources_path) as f:
        return json.load(f)


def fetch_github_docs(repo: str, docs_path: str) -> list[tuple[str, str]]:
    """Fetch all markdown files from a GitHub repo docs directory.
    Returns list of (content, source_url) tuples."""
    results = []
    url = f"{GITHUB_API}/repos/{repo}/contents/{docs_path}"
    data = gh_get(url)
    if not data or not isinstance(data, list):
        print(f"  No docs found at {repo}/{docs_path}")
        return results

    md_files = [f for f in data if f.get("name", "").endswith(".md")]
    print(f"  Found {len(md_files)} markdown files in {repo}/{docs_path}")

    for file_info in md_files:
        try:
            content = gh_get(file_info["download_url"], raw=True)
            if content:
                source_url = file_info["html_url"]
                results.append((content, source_url))
        except Exception as exc:
            print(f"  Warning: failed to fetch {file_info['name']} ({exc})")
        time.sleep(SEARCH_DELAY)

    return results


def strip_html_tags(text: str) -> str:
    """Remove HTML tags, keep text content."""
    return re.sub(r"<[^>]+>", " ", text)


def fetch_url_content(url: str) -> list[tuple[str, str]]:
    """Fetch a URL and return [(content, source_url)]."""
    content = fetch_url(url)
    if not content:
        return []
    # Strip HTML if it looks like a web page
    if "<html" in content[:500].lower():
        content = strip_html_tags(content)
    return [(content, url)]


def fetch_all_sources(sources: list[dict]) -> dict[str, list[tuple[str, str]]]:
    """Fetch all sources grouped by agent. Returns {agent: [(content, source_url), ...]}."""
    by_agent: dict[str, list[tuple[str, str]]] = {}

    for source in sources:
        agent = source["agent"]
        if agent not in by_agent:
            by_agent[agent] = []

        print(f"\nFetching [{agent}] {source.get('repo') or source.get('url')}")

        if source["type"] == "github":
            docs = fetch_github_docs(source["repo"], source["docs_path"])
            by_agent[agent].extend(docs)
        elif source["type"] == "url":
            docs = fetch_url_content(source["url"])
            by_agent[agent].extend(docs)

        time.sleep(SEARCH_DELAY)

    return by_agent


# ---------------------------------------------------------------------------
# Step 3: Extract candidate tips
# ---------------------------------------------------------------------------


def extract_sentences(text: str) -> list[str]:
    """Split text into sentences, filtering out noise."""
    # Remove markdown headers, links, images, code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)      # code blocks
    text = re.sub(r"^\s*#{1,6}\s+", "", text, flags=re.MULTILINE)  # headers
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)      # images
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # links -> text

    # Split into sentences
    sentences = re.split(r"(?<=[.!])\s+", text)

    # Clean and filter
    results = []
    for s in sentences:
        s = s.strip()
        # Must be reasonable length (1-2 sentences worth)
        if len(s) < 30 or len(s) > 300:
            continue
        # Skip table rows, list markers only, etc.
        if s.startswith("|") or s.startswith("---"):
            continue
        results.append(s)

    return results


def score_sentence(sentence: str) -> int:
    """Score how likely a sentence is to be an actionable tip."""
    score = 0

    # Action verb at or near the start
    if ACTION_VERBS.search(sentence[:40]):
        score += 2

    # Count signal matches
    for pattern in TIP_SIGNALS:
        if pattern.search(sentence):
            score += 1

    return score


def extract_tips_from_content(
    content: str, source_url: str, agent: str, existing: set[str]
) -> list[dict]:
    """Extract candidate tips from a single document."""
    candidates = []
    sentences = extract_sentences(content)

    for sentence in sentences:
        score = score_sentence(sentence)
        if score < MIN_SIGNALS:
            continue

        # Dedup against existing tips
        if is_duplicate(sentence, existing):
            continue

        candidates.append({
            "agent": agent,
            "tip": sentence,
            "source": source_url,
            "score": score,
        })

    return candidates


# ---------------------------------------------------------------------------
# Step 4: Create GitHub Issue
# ---------------------------------------------------------------------------


def ensure_label():
    print(f"\nEnsuring label '{LABEL}' exists...")
    try:
        resp = requests.post(
            f"{GITHUB_API}/repos/{OWNER_REPO}/labels",
            headers=HEADERS,
            json={"name": LABEL, "color": "1d76db", "description": "Auto-discovered tip candidates"},
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


def deduplicate_candidates(candidates: list[dict]) -> list[dict]:
    """Remove near-duplicates within the candidate list itself."""
    seen: set[str] = set()
    unique = []
    for c in candidates:
        norm = normalize_for_dedup(c["tip"])
        words = set(norm.split())
        is_dup = False
        for s in seen:
            s_words = set(s.split())
            if not s_words:
                continue
            overlap = len(words & s_words)
            if overlap / min(len(words), len(s_words)) >= 0.6:
                is_dup = True
                break
        if not is_dup:
            seen.add(norm)
            unique.append(c)
    return unique


def create_issue(candidates: list[dict]):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    n = len(candidates)
    title = f"\U0001f4a1 Tips Discovery: {today} \u2014 {n} candidates found"

    # Group by agent
    by_agent: dict[str, list[dict]] = {}
    for c in candidates:
        agent = c["agent"]
        if agent not in by_agent:
            by_agent[agent] = []
        by_agent[agent].append(c)

    body_parts = [
        "## Tip Candidates\n",
        f"Auto-discovered on {today}. Review each candidate and edit into proper tip format before adding to `tips.json`.\n",
    ]

    idx = 1
    for agent in sorted(by_agent.keys()):
        tips = by_agent[agent]
        body_parts.append(f"### {agent} ({len(tips)} candidates)\n")

        for c in tips:
            body_parts.append(
                f"#### {idx}. Score: {c['score']}\n"
                f"- **Text**: {c['tip']}\n"
                f"- **Source**: {c['source']}\n"
            )
            idx += 1

    body_parts.append("---\n")
    body_parts.append(
        "### How to review\n"
        "1. Feed candidates to LLM with `tips/TIPS_GUIDELINES.md` for quality filtering\n"
        "2. Verify each tip against its source URL\n"
        "3. Rewrite into 1-2 sentence actionable format\n"
        "4. Add to `tips.json` with proper agent/tip/source fields\n"
    )
    body_parts.append("\n\U0001f916 Auto-generated by [discover-tips workflow]\n")

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
    print("Tips Discovery Script")
    print("=" * 60)

    # Step 1: Load existing tips
    existing = load_existing_tips()

    # Step 2: Load sources and fetch content
    sources = load_sources()
    by_agent = fetch_all_sources(sources)

    # Step 3: Extract candidates
    all_candidates: list[dict] = []
    for agent, docs in by_agent.items():
        print(f"\nExtracting tips for [{agent}] from {len(docs)} documents...")
        for content, source_url in docs:
            tips = extract_tips_from_content(content, source_url, agent, existing)
            all_candidates.extend(tips)

    print(f"\nTotal raw candidates: {len(all_candidates)}")

    # Sort by score descending
    all_candidates.sort(key=lambda x: x["score"], reverse=True)

    # Deduplicate within candidates
    all_candidates = deduplicate_candidates(all_candidates)
    print(f"After internal dedup: {len(all_candidates)}")

    # Limit
    all_candidates = all_candidates[:MAX_CANDIDATES_IN_ISSUE]

    # Step 4: Create issue
    if all_candidates:
        print(f"\n{'=' * 60}")
        print(f"Found {len(all_candidates)} candidates. Creating issue...")
        create_issue(all_candidates)
    else:
        print(f"\n{'=' * 60}")
        print("No new candidates found. No issue will be created.")

    print("\nDone.")


if __name__ == "__main__":
    main()
