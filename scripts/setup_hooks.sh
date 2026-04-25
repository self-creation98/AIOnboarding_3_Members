#!/bin/bash
# =============================================================
# AI Log Hook — Git pre-push hook installer
# Chạy 1 lần trên mỗi máy: bash scripts/setup_hooks.sh
# =============================================================
set -e

HOOK_FILE=".git/hooks/pre-push"

# Check if inside a git repo
if [ ! -d ".git" ]; then
    echo "❌ [ai-log] Not a git repository. Run this from the root of your project."
    exit 1
fi

cat > "$HOOK_FILE" << 'HOOKEOF'
#!/bin/bash
# =============================================================
# Pre-push hook: Enforce AI logging + submit logs to server
# Installed by: bash scripts/setup_hooks.sh
# =============================================================

LOG_FILE=".ai-log/session.jsonl"

echo ""
echo "🔍 [ai-log] Checking AI usage logs before push..."
echo ""

# --- Detect Python 3 ---
PY=""
for candidate in python3 python py; do
    if $candidate --version &> /dev/null 2>&1; then
        PY_VER=$($candidate -c "import sys; print(sys.version_info[0])" 2>/dev/null)
        if [ "$PY_VER" = "3" ]; then
            PY="$candidate"
            break
        fi
    fi
done
if [ -z "$PY" ]; then
    echo "❌ [ai-log] Python 3 not found. Install Python 3 and add to PATH."
    exit 1
fi

# --- Auto-scan Antigravity sessions ---
ANTIGRAVITY_DIR="$HOME/.gemini/antigravity/brain"
if [ -d "$ANTIGRAVITY_DIR" ] && [ -f "scripts/log_antigravity.py" ]; then
    echo "🔍 [ai-log] Scanning Antigravity sessions..."
    $PY scripts/log_antigravity.py --auto 2>&1 || echo "[ai-log] ⚠️  Antigravity scan skipped."
    echo ""
fi

# --- Check 1: Log file exists and is not empty ---
if [ ! -f "$LOG_FILE" ] || [ ! -s "$LOG_FILE" ]; then
    echo "❌ [ai-log] BLOCKED: No AI logs found!"
    echo ""
    echo "   Bạn chưa ghi log sử dụng AI nào trong phiên làm việc này."
    echo "   Mọi thành viên đều PHẢI ghi log AI trước khi push."
    echo ""
    echo "   Cách ghi log:"
    echo "   ─────────────────────────────────────────────────"
    echo "   📌 Tool có hook tự động (Claude Code, Cursor, Codex, Gemini CLI, Copilot):"
    echo "       → Đảm bảo đã chạy: bash scripts/setup_hooks.sh"
    echo ""
    echo "   📌 Antigravity IDE:"
    echo "       → $PY scripts/log_antigravity.py --auto"
    echo ""
    echo "   📌 ChatGPT, Gemini Web, hoặc tool khác:"
    echo "       → $PY scripts/log_manual.py"
    echo ""
    echo "   Sau khi ghi log, hãy push lại."
    echo ""
    exit 1
fi

# --- Check 2: Count entries ---
ENTRY_COUNT=$(wc -l < "$LOG_FILE" | tr -d ' ')
if [ "$ENTRY_COUNT" -lt 1 ]; then
    echo "❌ [ai-log] BLOCKED: Log file exists but has no valid entries."
    exit 1
fi

echo "✅ [ai-log] Found $ENTRY_COUNT log entries."

# --- Check 3: Show who logged ---
echo ""
echo "📋 Các tool AI đã ghi log:"
$PY -c "
import json
from collections import Counter
tools = Counter()
with open('.ai-log/session.jsonl') as f:
    for line in f:
        try:
            e = json.loads(line.strip())
            tools[e.get('tool','unknown')] += 1
        except: pass
for t, c in tools.most_common():
    print(f'   - {t}: {c} entries')
" 2>/dev/null || echo "   (could not parse log details)"

# --- Submit to server ---
echo ""
echo "📤 [ai-log] Submitting logs to grading server..."
$PY scripts/submit_log.py 2>&1 || echo "[ai-log] ⚠️  Submit failed — logs kept locally."

echo ""
echo "✅ [ai-log] Push allowed. Happy coding! 🚀"
exit 0
HOOKEOF

chmod +x "$HOOK_FILE"
echo "[ai-log] ✅ Git pre-push hook installed."

# Create .ai-log directory
mkdir -p .ai-log
touch .ai-log/.gitkeep

echo "[ai-log] ✅ Setup complete."
echo ""
echo "📌 Hướng dẫn cho team:"
echo "   • Claude Code, Cursor, Codex, Gemini CLI, Copilot → log tự động"
echo "   • Antigravity → semi-auto (pre-push hook tự scan, hoặc: python scripts/log_antigravity.py --auto)"
echo "   • ChatGPT, Gemini Web, tool khác → python scripts/log_manual.py"
echo ""
echo "⚠️  Push sẽ bị CHẶN nếu không có AI log. Mọi người đều phải ghi log!"
