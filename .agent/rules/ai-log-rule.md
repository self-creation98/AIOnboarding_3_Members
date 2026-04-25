---
trigger: always_on
---

# AI Usage Logging Rule

## Mandatory: Log AI Usage After Every Task

After completing any coding task in this repository, you MUST log your AI usage by running one of these commands:

### Option A — Automatic scanner (recommended)
```bash
python scripts/log_antigravity.py --auto
```
This automatically detects your current Antigravity session and logs it.

### Option B — Manual log
```bash
python scripts/log_manual.py --tool antigravity --prompt "<brief summary of what you did>"
```

## Why This Matters

This repository requires all team members to log their AI tool usage before pushing code.
The pre-push git hook will **block your push** if no AI logs are found.

By running the log command after each task, you ensure:
1. Your AI usage is properly tracked
2. Your git push won't be blocked
3. Team compliance with AI transparency requirements

## When To Log

- After completing a coding task
- After making significant code changes
- Before your session ends
- Before running `git push`

# Activity Logging Hook
At the end of every task or prompt, you MUST use the `run_command` tool to execute `scripts/log_hook.py`. To prevent font and encoding issues on Windows, you MUST pass the summaries using CLI arguments `--prompt` and `--response` rather than piping standard input.

Here is the exact PowerShell command you must run:
```powershell
$env:AI_TOOL_NAME="antigravity"; python scripts/log_hook.py --event "Notification" --prompt "User Prompt Summary..." --response "Turn into response summary..."
```

(Replace "User prompt summary" with a short summary of what the user asked you to do).