#!/usr/bin/env bash
# =============================================================================
# Script: remove_config_from_history.sh
# Purpose: Remove sensitive config.yml file from entire Git history
# Author: SynthQuant DevOps Team
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# SAFETY WARNING
# =============================================================================
echo ""
echo -e "${RED}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║                                                                              ║${NC}"
echo -e "${RED}║   ⚠️   WARNING: DESTRUCTIVE OPERATION - READ CAREFULLY   ⚠️                  ║${NC}"
echo -e "${RED}║                                                                              ║${NC}"
echo -e "${RED}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}This script will PERMANENTLY REWRITE your Git history to remove config.yml.${NC}"
echo ""
echo -e "${YELLOW}BEFORE PROCEEDING, you MUST:${NC}"
echo ""
echo -e "  ${BLUE}1.${NC} Create a BACKUP of this repository:"
echo -e "     ${GREEN}git clone --mirror <repo-url> backup-repo.git${NC}"
echo ""
echo -e "  ${BLUE}2.${NC} Notify ALL team members that history will be rewritten"
echo ""
echo -e "  ${BLUE}3.${NC} Ensure all team members have pushed their changes"
echo ""
echo -e "  ${BLUE}4.${NC} After this operation, ALL team members must:"
echo -e "     ${GREEN}git fetch --all${NC}"
echo -e "     ${GREEN}git reset --hard origin/main${NC}"
echo ""
echo -e "${RED}This operation CANNOT be undone without the backup!${NC}"
echo ""
read -p "Have you backed up the repository and notified your team? (yes/no): " CONFIRM

if [[ "$CONFIRM" != "yes" ]]; then
    echo -e "${RED}Operation cancelled. Please backup your repository first.${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}Proceeding with history rewrite...${NC}"
echo ""

# =============================================================================
# TOOL DETECTION
# =============================================================================
GIT_FILTER_REPO=""
BFG=""

# Check for git-filter-repo (preferred)
if command -v git-filter-repo &> /dev/null; then
    GIT_FILTER_REPO="git-filter-repo"
    echo -e "${GREEN}✓ Found git-filter-repo${NC}"
elif command -v git filter-repo &> /dev/null; then
    GIT_FILTER_REPO="git filter-repo"
    echo -e "${GREEN}✓ Found git filter-repo${NC}"
fi

# Check for BFG
if command -v bfg &> /dev/null; then
    BFG="bfg"
    echo -e "${GREEN}✓ Found BFG Repo-Cleaner${NC}"
fi

# =============================================================================
# EXECUTION
# =============================================================================
if [[ -n "$GIT_FILTER_REPO" ]]; then
    echo ""
    echo -e "${BLUE}Using git-filter-repo (recommended)...${NC}"
    echo ""
    
    # Run git-filter-repo to remove config.yml from all history
    $GIT_FILTER_REPO --path config.yml --invert-paths --force
    
    echo ""
    echo -e "${GREEN}✓ Successfully removed config.yml from history using git-filter-repo${NC}"

elif [[ -n "$BFG" ]]; then
    echo ""
    echo -e "${BLUE}Using BFG Repo-Cleaner...${NC}"
    echo ""
    
    # First, ensure config.yml is deleted from HEAD
    if [[ -f "config.yml" ]]; then
        git rm --cached config.yml 2>/dev/null || true
        git commit -m "chore: remove config.yml from tracking" 2>/dev/null || true
    fi
    
    # Run BFG to delete the file from history
    $BFG --delete-files config.yml --no-blob-protection
    
    # Clean up refs and garbage collect
    echo ""
    echo -e "${BLUE}Cleaning up refs and running garbage collection...${NC}"
    git reflog expire --expire=now --all
    git gc --prune=now --aggressive
    
    echo ""
    echo -e "${GREEN}✓ Successfully removed config.yml from history using BFG${NC}"

else
    # Neither tool found - print installation instructions
    echo ""
    echo -e "${RED}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║   ERROR: No history rewriting tool found!                                    ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Please install one of the following tools:${NC}"
    echo ""
    echo -e "${BLUE}Option 1: git-filter-repo (Recommended)${NC}"
    echo -e "  ${GREEN}# Using pip:${NC}"
    echo -e "  pip install git-filter-repo"
    echo ""
    echo -e "  ${GREEN}# Using Homebrew (macOS):${NC}"
    echo -e "  brew install git-filter-repo"
    echo ""
    echo -e "  ${GREEN}# Using apt (Debian/Ubuntu):${NC}"
    echo -e "  sudo apt install git-filter-repo"
    echo ""
    echo -e "${BLUE}Option 2: BFG Repo-Cleaner${NC}"
    echo -e "  ${GREEN}# Using Homebrew (macOS):${NC}"
    echo -e "  brew install bfg"
    echo ""
    echo -e "  ${GREEN}# Manual download:${NC}"
    echo -e "  # Download from: https://rtyley.github.io/bfg-repo-cleaner/"
    echo -e "  # Requires Java Runtime Environment (JRE)"
    echo ""
    exit 1
fi

# =============================================================================
# POST-PROCESSING INSTRUCTIONS
# =============================================================================
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   ✓ HISTORY REWRITE COMPLETE                                                 ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}NEXT STEPS:${NC}"
echo ""
echo -e "${BLUE}1.${NC} Verify the changes locally:"
echo -e "   ${GREEN}git log --all --full-history -- config.yml${NC}"
echo -e "   (This should return no results if successful)"
echo ""
echo -e "${BLUE}2.${NC} Force push to remote (THIS WILL OVERWRITE REMOTE HISTORY):"
echo -e "   ${GREEN}git push origin --force --all${NC}"
echo -e "   ${GREEN}git push origin --force --tags${NC}"
echo ""
echo -e "${BLUE}3.${NC} If using GitHub/GitLab, also clear their caches:"
echo -e "   - GitHub: Contact support or wait for cache expiration"
echo -e "   - GitLab: Go to Settings > Repository > Clean up repository"
echo ""
echo -e "${BLUE}4.${NC} Notify ALL team members to re-clone or reset their local repos:"
echo -e "   ${GREEN}# Option A: Fresh clone (recommended)${NC}"
echo -e "   git clone <repo-url>"
echo ""
echo -e "   ${GREEN}# Option B: Reset existing repo${NC}"
echo -e "   git fetch --all"
echo -e "   git reset --hard origin/main"
echo ""
echo -e "${BLUE}5.${NC} Share the new config.example.yml with your team:"
echo -e "   - Each developer should copy it to config.yml"
echo -e "   - Fill in their own secrets"
echo -e "   - config.yml is now in .gitignore and won't be tracked"
echo ""
echo -e "${BLUE}6.${NC} Rotate ALL secrets that were exposed:"
echo -e "   - Generate new API keys"
echo -e "   - Update ADMIN_SECRET"
echo -e "   - Update ALPHA_VANTAGE_API_KEY"
echo ""
echo -e "${RED}⚠️  IMPORTANT: Consider any secrets in the old history as COMPROMISED!${NC}"
echo -e "${RED}   Even after removal, they may exist in forks, caches, or backups.${NC}"
echo ""
