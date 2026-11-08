#!/bin/sh
# Commit what's staged and push it, for the GitHub Actions workflows.
# Usage: sh tools/push.sh "commit message"
#
# Several workflows commit to main (photos and new cards, community
# suggestions, the weekly lists). If another one pushed first, this rebases
# onto it, keeping this run's version of any file both changed, then rebuilds
# the generated files (index.html, data/site) from the combined data, so two
# runs never leave each other's changes out.
set -e
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
if git diff --cached --quiet; then echo "Nothing new to commit"; exit 0; fi
git commit -q -m "$1"
for i in 1 2 3 4 5; do
  if git push -q; then echo "Pushed"; exit 0; fi
  echo "Another workflow pushed first; rebasing and rebuilding (try $i)"
  sleep $((i * 5))
  git fetch -q origin main
  if ! git rebase -q -X theirs origin/main; then git rebase --abort; echo "Rebase failed"; exit 1; fi
  "${PYTHON:-python3}" src/build.py > /dev/null
  git add -A index.html data/site
  git diff --cached --quiet || git commit -q --amend --no-edit
done
echo "Couldn't push after 5 tries"
exit 1
