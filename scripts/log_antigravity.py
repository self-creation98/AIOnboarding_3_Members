#!/usr/bin/env python3
"""
Antigravity IDE log scanner — extracts AI usage logs from Antigravity's
conversation history stored in ~/.gemini/antigravity/brain/.

Unlike other AI tools (Claude Code, Cursor, etc.) that have hook APIs,
Antigravity does NOT read .gemini/settings.json (that's for Gemini CLI).
Antigravity uses .agent/rules/ and .agent/workflows/ for behavioral guidance,
but has no programmatic hook system.

This script bridges the gap by scanning Antigravity's local conversation data
and extracting log entries in the standard AI-Log-Hook format.

Usage:
  python scripts/log_antigravity.py --auto           # Auto-scan recent sessions for this repo
  python scripts/log_antigravity.py --hours 48        # Scan last 48 hours
  python scripts/log_antigravity.py --conversation-id <id>  # Scan specific conversation
  python scripts/log_antigravity.py --all             # Scan all unlogged conversations

How it works:
  1. Finds Antigravity brain directory (~/.gemini/antigravity/brain/)
  2. Scans conversation directories for this repo's workspace
  3. Extracts metadata: timestamps, prompts, models
  4. Writes entries to .ai-log/session.jsonl (standard format)
"""
import json
import os
import sys
import subprocess
import argparse
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Fix Windows console encoding for emoji output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

VN_TZ = timezone(timedelta(hours=7))

BRAIN_PATHS = {
    "win32": Path.home() / ".gemini" / "antigravity" / "brain",
    "darwin": Path.home() / ".gemini" / "antigravity" / "brain",
    "linux": Path.home() / ".gemini" / "antigravity" / "brain",
}


def git(cmd):
    try:
        return subprocess.check_output(
            cmd.split(), shell=False, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return ""


def get_brain_dir() -> Path | None:
    """Find the Antigravity brain directory."""
    env_path = os.environ.get("ANTIGRAVITY_BRAIN_DIR")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p

    p = BRAIN_PATHS.get(sys.platform, BRAIN_PATHS["linux"])
    if p.exists():
        return p
    return None


def get_repo_identifiers() -> list[str]:
    """Get identifiers to match conversations to this repo."""
    identifiers = []

    # Repo name from git remote
    remote = git("git remote get-url origin")
    if remote:
        repo_name = remote.split("/")[-1].replace(".git", "")
        identifiers.append(repo_name)
        # Also add the full path component (org/repo)
        parts = remote.rstrip("/").split("/")
        if len(parts) >= 2:
            identifiers.append(f"{parts[-2]}/{parts[-1]}".replace(".git", ""))

    # Current working directory name
    cwd = Path.cwd()
    identifiers.append(cwd.name)
    # Full path for workspace matching
    identifiers.append(str(cwd).replace("\\", "/").lower())
    identifiers.append(str(cwd).lower())

    return [i for i in identifiers if i]


def get_logged_conversation_ids(log_file: Path) -> set[str]:
    """Read already-logged conversation IDs from session.jsonl."""
    logged = set()
    if not log_file.exists():
        return logged
    with open(log_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("tool") == "antigravity":
                    sid = entry.get("session_id", "")
                    if sid:
                        logged.add(sid)
            except json.JSONDecodeError:
                pass
    return logged


def scan_conversation(conv_dir: Path, repo_ids: list[str]) -> dict | None:
    """
    Scan a conversation directory to determine if it's related to this repo.
    Returns conversation metadata if relevant, None otherwise.
    """
    conv_id = conv_dir.name

    # Skip non-UUID directories
    if not re.match(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$", conv_id):
        return None

    def _match_content(content: str) -> bool:
        content_lower = content.lower()
        for rid in repo_ids:
            if rid.lower() in content_lower:
                return True
        return False

    # Strategy 1: Check overview.txt for workspace references
    logs_dir = conv_dir / ".system_generated" / "logs"
    overview = logs_dir / "overview.txt"
    if overview.exists():
        try:
            content = overview.read_text(encoding="utf-8", errors="ignore")[:50000]
            if _match_content(content):
                return _extract_conversation_data(conv_dir, conv_id, content)
        except Exception:
            pass

    # Strategy 2: Check ALL markdown files in conversation root
    # (includes project_overview.md, task.md, walkthrough.md, implementation_plan.md, etc.)
    try:
        for md_file in conv_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")[:20000]
                if _match_content(content):
                    return _extract_conversation_data(conv_dir, conv_id)
            except Exception:
                pass
    except Exception:
        pass

    # Strategy 3: Check metadata JSON files for workspace/repo references
    try:
        for json_file in conv_dir.glob("*.metadata.json"):
            try:
                content = json_file.read_text(encoding="utf-8", errors="ignore")
                if _match_content(content):
                    return _extract_conversation_data(conv_dir, conv_id)
            except Exception:
                pass
    except Exception:
        pass

    # Strategy 4: Check step content files for workspace references
    steps_dir = conv_dir / ".system_generated" / "steps"
    if steps_dir.exists():
        try:
            step_dirs = sorted(steps_dir.iterdir(), key=lambda d: d.name)
            # Check first 5 and last 5 steps (most likely to contain workspace info)
            check_dirs = list(step_dirs[:5]) + list(step_dirs[-5:])
            # Remove duplicates while preserving order
            seen = set()
            unique_dirs = []
            for d in check_dirs:
                if d.name not in seen:
                    seen.add(d.name)
                    unique_dirs.append(d)
            for step_dir in unique_dirs:
                content_file = step_dir / "content.md"
                if content_file.exists():
                    try:
                        content = content_file.read_text(encoding="utf-8", errors="ignore")[:10000]
                        if _match_content(content):
                            return _extract_conversation_data(conv_dir, conv_id)
                    except Exception:
                        pass
        except Exception:
            pass

    return None


def _extract_conversation_data(conv_dir: Path, conv_id: str, overview_content: str = "") -> dict:
    """Extract metadata from a conversation directory."""
    data = {
        "conversation_id": conv_id,
        "conv_dir": conv_dir,
        "prompts": [],
        "timestamps": [],
        "title": "",
    }

    # Try to extract title from overview
    if overview_content:
        lines = overview_content.split("\n")
        for line in lines[:20]:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("---"):
                # First non-empty, non-heading line is likely a prompt/title
                if len(line) > 10 and len(line) < 500:
                    data["title"] = line[:200]
                    break

    # Get conversation modification times for timestamp
    try:
        mtime = conv_dir.stat().st_mtime
        data["timestamps"].append(
            datetime.fromtimestamp(mtime, tz=VN_TZ).isoformat()
        )
    except Exception:
        data["timestamps"].append(datetime.now(VN_TZ).isoformat())

    # Try to extract prompts from step content files
    steps_dir = conv_dir / ".system_generated" / "steps"
    if steps_dir.exists():
        try:
            step_dirs = sorted(steps_dir.iterdir(), key=lambda d: d.name)
            for step_dir in step_dirs[:5]:  # First 5 steps
                content_file = step_dir / "content.md"
                if content_file.exists():
                    content = content_file.read_text(encoding="utf-8", errors="ignore")[:2000]
                    # Extract title or first meaningful line
                    for line in content.split("\n"):
                        line = line.strip()
                        if line.startswith("Title:"):
                            data["prompts"].append(line.replace("Title:", "").strip()[:200])
                            break
                        elif line.startswith("# "):
                            data["prompts"].append(line.replace("# ", "").strip()[:200])
                            break
        except Exception:
            pass

    # Check artifact files for task summary
    for artifact_name in ["task.md", "walkthrough.md", "implementation_plan.md"]:
        artifact = conv_dir / artifact_name
        if artifact.exists():
            try:
                content = artifact.read_text(encoding="utf-8", errors="ignore")
                # Extract first heading as task summary
                for line in content.split("\n"):
                    line = line.strip()
                    if line.startswith("# "):
                        summary = line.replace("# ", "").strip()[:200]
                        if summary and summary not in data["prompts"]:
                            data["prompts"].insert(0, summary)
                        break
            except Exception:
                pass

    # Check metadata files for additional info
    for meta_name in ["task.md.metadata.json", "implementation_plan.md.metadata.json"]:
        meta_file = conv_dir / meta_name
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                summary = meta.get("Summary", "")
                if summary and len(summary) > 10:
                    if summary[:100] not in [p[:100] for p in data["prompts"]]:
                        data["prompts"].append(summary[:300])
            except Exception:
                pass

    return data


def create_log_entries(conv_data: dict) -> list[dict]:
    """Create standardized log entries from conversation data."""
    student = git("git config user.email")
    if not student:
        student = os.environ.get("USERNAME", os.environ.get("USER", "unknown"))

    repo = git("git remote get-url origin").split("/")[-1].replace(".git", "")
    branch = git("git rev-parse --abbrev-ref HEAD")
    commit = git("git rev-parse --short HEAD")

    entries = []
    conv_id = conv_data["conversation_id"]
    ts = conv_data["timestamps"][0] if conv_data["timestamps"] else datetime.now(VN_TZ).isoformat()

    # Create one entry per conversation with combined prompt summary
    prompts = conv_data["prompts"]
    if not prompts:
        prompt_summary = conv_data.get("title", "Antigravity session (no prompt extracted)")
    else:
        prompt_summary = " | ".join(prompts[:5])  # Combine up to 5 prompts

    entry = {
        "ts": ts,
        "tool": "antigravity",
        "event": "SessionScan",
        "session_id": conv_id,
        "entry_id": f"antigravity-{conv_id[:8]}-{datetime.now(VN_TZ).strftime('%Y%m%d-%H%M%S')}",
        "model": "gemini",  # Antigravity uses Gemini models
        "repo": repo if repo else Path.cwd().name,
        "branch": branch,
        "commit": commit,
        "student": student,
        "prompt": prompt_summary[:1000],
        "response_summary": f"Scanned from Antigravity conversation {conv_id}",
        "scan_source": "log_antigravity.py",
    }
    entries.append(entry)

    return entries


def main():
    parser = argparse.ArgumentParser(
        description="Antigravity IDE log scanner — extract AI usage from conversation history"
    )
    parser.add_argument(
        "--auto", action="store_true",
        help="Auto-scan recent sessions for this repo (default: last 24 hours)"
    )
    parser.add_argument(
        "--hours", type=int, default=24,
        help="Number of hours to look back (default: 24)"
    )
    parser.add_argument(
        "--conversation-id",
        help="Scan a specific conversation by ID"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Scan all conversations, not just recent ones"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be logged without writing"
    )
    args = parser.parse_args()

    # Default to --auto if no mode specified
    if not args.auto and not args.conversation_id and not args.all:
        args.auto = True

    # Find brain directory
    brain_dir = get_brain_dir()
    if not brain_dir:
        print("[antigravity-log] ⚠️  Antigravity brain directory not found.", file=sys.stderr)
        print("[antigravity-log]    Expected: ~/.gemini/antigravity/brain/", file=sys.stderr)
        print("[antigravity-log]    Set ANTIGRAVITY_BRAIN_DIR env var if in custom location.", file=sys.stderr)
        sys.exit(0)  # Don't block — graceful exit

    # Setup log file
    log_dir = Path(os.environ.get("AI_LOG_DIR", ".ai-log"))
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "session.jsonl"

    # Get already-logged conversations
    logged_ids = get_logged_conversation_ids(log_file)

    # Get repo identifiers for matching
    repo_ids = get_repo_identifiers()
    if not repo_ids:
        print("[antigravity-log] ⚠️  Cannot determine repo identity. Run from a git repo.", file=sys.stderr)
        sys.exit(0)

    # Determine which conversations to scan
    cutoff = None
    if args.auto or args.hours:
        cutoff = datetime.now(tz=VN_TZ) - timedelta(hours=args.hours)

    all_entries = []

    if args.conversation_id:
        # Scan specific conversation
        conv_dir = brain_dir / args.conversation_id
        if not conv_dir.exists():
            print(f"[antigravity-log] ❌ Conversation not found: {args.conversation_id}", file=sys.stderr)
            sys.exit(1)
        conv_data = _extract_conversation_data(conv_dir, args.conversation_id)
        if conv_data and args.conversation_id not in logged_ids:
            all_entries.extend(create_log_entries(conv_data))
    else:
        # Scan all conversation directories
        try:
            conv_dirs = [d for d in brain_dir.iterdir() if d.is_dir()]
        except PermissionError:
            print("[antigravity-log] ❌ Permission denied reading brain directory.", file=sys.stderr)
            sys.exit(0)

        for conv_dir in conv_dirs:
            conv_id = conv_dir.name

            # Skip already logged
            if conv_id in logged_ids:
                continue

            # Skip old conversations if cutoff set
            if cutoff and not args.all:
                try:
                    mtime = datetime.fromtimestamp(conv_dir.stat().st_mtime, tz=VN_TZ)
                    if mtime < cutoff:
                        continue
                except Exception:
                    continue

            # Try to match conversation to this repo
            conv_data = scan_conversation(conv_dir, repo_ids)
            if conv_data:
                entries = create_log_entries(conv_data)
                all_entries.extend(entries)

    if not all_entries:
        print("[antigravity-log] ℹ️  No new Antigravity sessions found for this repo.", file=sys.stderr)
        sys.exit(0)

    if args.dry_run:
        print(f"\n[antigravity-log] 🔍 DRY RUN — Would log {len(all_entries)} entries:\n")
        for entry in all_entries:
            print(f"  • [{entry['session_id'][:8]}...] {entry['prompt'][:80]}")
        sys.exit(0)

    # Write entries
    with open(log_file, "a", encoding="utf-8") as f:
        for entry in all_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"\n[antigravity-log] ✅ Logged {len(all_entries)} Antigravity session(s).")
    for entry in all_entries:
        print(f"  • [{entry['session_id'][:8]}...] {entry['prompt'][:80]}")
    print(f"[antigravity-log] 📁 Saved to: {log_file}")


if __name__ == "__main__":
    main()
