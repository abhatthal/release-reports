#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional

import requests

try:
    from google import genai
except Exception:
    genai = None


GITHUB_API_BASE = "https://api.github.com"


def github_get_json(url: str, token: Optional[str] = None) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "release-report-generator",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()


def parse_dt(value: Optional[str]) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fetch_all_releases(owner: str, repo: str, token: Optional[str] = None) -> List[Dict[str, Any]]:
    releases: List[Dict[str, Any]] = []
    page = 1
    per_page = 100

    while True:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/releases?per_page={per_page}&page={page}"
        batch = github_get_json(url, token=token)

        if not isinstance(batch, list):
            raise RuntimeError(f"Unexpected GitHub API response on page {page}")

        if not batch:
            break

        releases.extend(batch)

        if len(batch) < per_page:
            break

        page += 1

    # Enforce latest -> oldest regardless of API behavior.
    releases.sort(
        key=lambda rel: parse_dt(rel.get("published_at") or rel.get("created_at")),
        reverse=True,
    )
    return releases


def display_release_name(rel: Dict[str, Any]) -> str:
    return str(rel.get("name") or rel.get("tag_name") or "untitled release").strip()


def print_usage_and_exit(parser: argparse.ArgumentParser, message: str, code: int = 2) -> None:
    print(f"Error: {message}\n", file=sys.stderr)
    parser.print_help(sys.stderr)
    raise SystemExit(code)


def default_output_name(owner: str, repo: str) -> str:
    # safe_owner = re.sub(r"[^A-Za-z0-9._-]+", "-", owner.strip())
    safe_repo = re.sub(r"[^A-Za-z0-9._-]+", "-", repo.strip())
    # return f"{safe_owner}-{safe_repo}-release-report.md"
    return f"{safe_repo}-release-report.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="release_report.py",
        description="Generate a Markdown report from GitHub releases.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python release_report.py OWNER REPO\n"
            "  python release_report.py OWNER REPO --output report.md\n"
            "  GITHUB_TOKEN=... python release_report.py OWNER REPO\n"
        ),
    )

    parser.add_argument("owner", help="GitHub owner or organization name")
    parser.add_argument("repo", help="GitHub repository name")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Optional output Markdown file. If omitted, the name is derived from OWNER and REPO.",
    )
    parser.add_argument(
        "--github-token",
        default=os.getenv("GITHUB_TOKEN"),
        help="Optional GitHub token (recommended for higher rate limits)",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        help="Gemini model name (default: gemini-2.5-flash)",
    )

    args = parser.parse_args()

    if not args.owner.strip():
        print_usage_and_exit(parser, "OWNER cannot be empty.")
    if not args.repo.strip():
        print_usage_and_exit(parser, "REPO cannot be empty.")

    return args


def summarize_release_changes(
    current: Dict[str, Any],
    older: Optional[Dict[str, Any]],
    model: str,
) -> str:
    current_name = display_release_name(current)
    current_tag = current.get("tag_name") or ""
    current_notes = current.get("body") or ""

    # If the Gemini SDK is unavailable, skip AI and use the fallback.
    if genai is not None:
        try:
            client = genai.Client()

            if older is None:
                prompt = f"""
Write a concise release summary for a Markdown report.

Release: {current_name}
Tag: {current_tag}

Summarize only the most important user-visible points.
Do not repeat the full release notes.
Keep it to 3 to 5 bullets.
""".strip()
            else:
                older_name = display_release_name(older)
                older_tag = older.get("tag_name") or ""

                prompt = f"""
Write a concise release summary for a Markdown report.

Summarize only what changed from the older release to the newer one.
Focus on new features, bug fixes, deprecations, removals, and breaking changes.
Do not repeat the full release notes.
Do not invent details.
Keep it to 3 to 5 bullets.

Older release:
- Name: {older_name}
- Tag: {older_tag}

Newer release:
- Name: {current_name}
- Tag: {current_tag}

Newer release notes:
{current_notes}
""".strip()

            response = client.models.generate_content(model=model, contents=prompt)
            text = (response.text or "").strip()
            if text:
                return text

        except Exception:
            pass  # fall through to fallback

    # Fallback behavior if no API key, SDK issue, or API failure.
    if not current_notes.strip():
        return "_No release notes available._"

    bullet_lines = [
        line.strip()
        for line in current_notes.splitlines()
        if line.strip().startswith(("-", "*"))
    ]

    if not bullet_lines:
        bullet_lines = [line.strip() for line in current_notes.splitlines() if line.strip()][:5]

    if not bullet_lines:
        return "_No release notes available._"

    return "\n".join(f"- {line.lstrip('-* ').strip()}" for line in bullet_lines[:5])


def fmt_asset_block(asset: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    name = asset.get("name") or "unnamed asset"

    lines.append(f"## {name}")
    lines.append("")
    if asset.get("browser_download_url"):
        url = asset["browser_download_url"]
        lines.append(f"- Download: [{url}]({url})")
    if asset.get("content_type"):
        lines.append(f"- Content type: `{asset['content_type']}`")
    if asset.get("size") is not None:
        lines.append(f"- Size: `{asset['size']}` bytes")
    if asset.get("download_count") is not None:
        lines.append(f"- Downloads: `{asset['download_count']}`")
    if asset.get("digest"):
        lines.append(f"- Digest: `{asset['digest']}`")
    if asset.get("created_at"):
        lines.append(f"- Created: `{asset['created_at']}`")
    if asset.get("updated_at"):
        lines.append(f"- Updated: `{asset['updated_at']}`")

    uploader = asset.get("uploader") or {}
    if uploader.get("login"):
        lines.append(f"- Uploader: `{uploader['login']}`")

    return lines


def write_markdown_report(
    owner: str,
    repo: str,
    releases: List[Dict[str, Any]],
    output_path: str,
    model: str,
) -> None:
    lines: List[str] = []
    now = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z")

    lines.append(f"# Release report for `{owner}/{repo}`")
    lines.append("")
    lines.append(f"_Generated on {now}_")
    lines.append("")
    lines.append("Releases are listed from latest to oldest.")
    lines.append("")
    lines.append("Release changelists are an AI-generated summary. Visit release pages to see the full release notes.")
    lines.append("")

    # releases is already sorted newest -> oldest
    for idx, release in enumerate(releases):
        older_release = releases[idx + 1] if idx + 1 < len(releases) else None

        lines.append(f"# {display_release_name(release)}")
        lines.append("")
        if release.get("tag_name"):
            lines.append(f"- Tag: `{release['tag_name']}`")
        if release.get("published_at"):
            lines.append(f"- Published: `{release['published_at']}`")
        if release.get("html_url"):
            lines.append(f"- Release page: {release['html_url']}")
        lines.append("")
        lines.append("**Relevant changes since the previous release**")
        lines.append("")
        lines.append(summarize_release_changes(release, older_release, model=model))
        lines.append("")

        assets = release.get("assets") or []
        if not assets:
            lines.append("_No assets were published with this release._")
            lines.append("")
            continue

        for asset in assets:
            lines.extend(fmt_asset_block(asset))
            lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def main() -> int:
    try:
        args = parse_args()
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    try:
        releases = fetch_all_releases(args.owner, args.repo, token=args.github_token)
        if not releases:
            print(f"No releases found for {args.owner}/{args.repo}", file=sys.stderr)

        output_path = args.output or default_output_name(args.owner, args.repo)

        write_markdown_report(
            owner=args.owner,
            repo=args.repo,
            releases=releases,
            output_path=output_path,
            model=args.model,
        )
        print(f"Wrote {len(releases)} releases to {output_path}")
        return 0
    except requests.HTTPError as e:
        print(f"GitHub API error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())