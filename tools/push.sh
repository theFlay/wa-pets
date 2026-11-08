#!/bin/sh
# Commit what's staged and push it, for the GitHub Actions workflows.
# Usage: sh tools/push.sh "commit message"
#
# Several workflows commit data to main (photos and new cards, community
# suggestions, the weekly lists). If another one pushed first, this rebases
# onto it, keeping this run's version of any line both changed. The built
# site isn't committed (the Deploy site workflow builds it), so the only
# files two runs can both touch are data files with one entry per line.
# Writes pushed=true to the step's outputs when it pushed something.
set -e
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
if git diff --cached --quiet; then echo "Nothing new to commit"; exit 0; fi
git commit -q -m "$1"
for i in 1 2 3 4 5; do
  if git push -q; then
    echo "Pushed"
    [ -n "$GITHUB_OUTPUT" ] && echo "pushed=true" >> "$GITHUB_OUTPUT"
    exit 0
  fi
  echo "Another workflow pushed first; rebasing (try $i)"
  sleep $((i * 5))
  git fetch -q origin main
  if ! git rebase -q -X theirs origin/main; then git rebase --abort; echo "Rebase failed"; exit 1; fi
done
echo "Couldn't push after 5 tries"
exit 1
