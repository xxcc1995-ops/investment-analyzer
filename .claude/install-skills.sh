#!/bin/bash
# Install Claude Code skills from project to user directory
# Usage: bash .claude/install-skills.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USER_SKILLS_DIR="$HOME/.claude/skills"

echo "Installing Claude Code skills..."

# Create user skills directory if not exists
mkdir -p "$USER_SKILLS_DIR"

# Copy each skill
for skill_dir in "$SCRIPT_DIR/skills"/*/; do
    if [ -d "$skill_dir" ]; then
        skill_name=$(basename "$skill_dir")
        echo "  Installing: $skill_name"
        cp -r "$skill_dir" "$USER_SKILLS_DIR/"
    fi
done

echo ""
echo "Done! Skills installed to: $USER_SKILLS_DIR"
echo "Restart Claude Code to use the new skills."
