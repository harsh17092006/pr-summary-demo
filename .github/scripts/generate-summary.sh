#!/bin/bash

set -euo pipefail
set -x

# Clean up temporary files on exit
trap 'rm -f pr_diff.txt summary.txt response_debug.txt' EXIT

# Check dependencies
command -v jq >/dev/null || { echo "❌ jq not installed."; exit 2; }
command -v gh >/dev/null || { echo "❌ gh not installed."; exit 2; }
[[ -n "${GROQ_API_KEY:-}" && "${#GROQ_API_KEY}" -ge 10 ]] || { echo "❌ GROQ_API_KEY invalid or missing."; exit 3; }

# Get default branch
DEFAULT_BRANCH=$(git remote show origin | grep "HEAD branch" | awk '{print $NF}')
[[ -n "$DEFAULT_BRANCH" ]] || { echo "❌ Could not determine default branch."; exit 1; }

# Check shallow status
echo "ℹ️ Checking if repository is shallow."
if [[ -f .git/shallow ]]; then
  echo "ℹ️ Shallow repository detected, attempting unshallow fetch."
  if ! git fetch --unshallow origin "$DEFAULT_BRANCH" 2>&1 | tee fetch_output.log; then
    if grep -q "does not make sense" fetch_output.log; then
      echo "ℹ️ Repository is already complete, falling back to regular fetch."
      git fetch origin "$DEFAULT_BRANCH" || { echo "❌ Failed to fetch origin/$DEFAULT_BRANCH."; exit 1; }
    else
      echo "❌ Failed to fetch origin/$DEFAULT_BRANCH (unshallow)."
      cat fetch_output.log
      exit 1
    fi
  fi
else
  echo "ℹ️ Repository is not shallow, performing regular fetch."
  git fetch origin "$DEFAULT_BRANCH" || { echo "❌ Failed to fetch origin/$DEFAULT_BRANCH."; exit 1; }
fi
git show-ref --verify --quiet refs/remotes/origin/"$DEFAULT_BRANCH" || { echo "❌ Branch origin/$DEFAULT_BRANCH not found."; exit 1; }

# Generate diff
if git merge-base origin/"$DEFAULT_BRANCH" HEAD >/dev/null; then
  git diff origin/"$DEFAULT_BRANCH"...HEAD > pr_diff.txt || { echo "❌ Failed to generate diff."; exit 1; }
else
  echo "⚠️ No merge base found. Generating full diff."
  git diff > pr_diff.txt || { echo "❌ Failed to generate full diff."; exit 1; }
fi

# Handle empty diff
if [[ ! -s pr_diff.txt ]]; then
  echo "No changes detected in the pull request." > summary.txt
  echo "✅ Summary generated (no changes)."
  exit 0
fi

# Process diff (truncate to 1000 lines)
if [[ $(wc -l < pr_diff.txt) -gt 1000 ]]; then
  echo "⚠️ Diff exceeds 1,000 lines; truncating."
  DIFF=$(head -n 1000 pr_diff.txt | iconv -c -t utf-8)
else
  DIFF=$(iconv -c -t utf-8 < pr_diff.txt)
fi
[[ -n "$DIFF" ]] || { echo "❌ iconv produced empty output."; exit 6; }

# Convert to JSON
DIFF_JSON=$(echo "$DIFF" | jq -Rs .) || { echo "❌ jq processing failed."; exit 6; }

# Prepare API payload
MODEL="${GROQ_MODEL:-llama3-70b-8192}"
DATA=$(jq -n --arg model "$MODEL" --arg diff "$DIFF" \
  '{ "model": $model, "messages": [ { "role": "system", "content": "Summarize GitHub pull request diffs concisely for reviewers, focusing on code changes, not filenames." }, { "role": "user", "content": $diff } ] }')

# Make API request with retries
for attempt in {1..3}; do
  RESPONSE=$(curl -s -w "%{http_code}" https://api.groq.com/openai/v1/chat/completions \
    -H "Authorization: Bearer $GROQ_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$DATA" -o response_body.txt)
  if [[ "$RESPONSE" == "429" ]]; then
    echo "⚠️ Rate limit hit, retrying ($attempt/3)..."
    sleep $((attempt * 5))
    continue
  fi
  break
done
[[ "$RESPONSE" == "200" ]] || { echo "❌ API request failed (status $RESPONSE): $(cat response_body.txt)"; exit 4; }
RESPONSE=$(cat response_body.txt)

# Save response for debugging
echo "$RESPONSE" > response_debug.txt

# Extract summary
echo "$RESPONSE" | jq -e '.choices[0].message.content' >/dev/null || { echo "❌ Invalid API response: $RESPONSE"; exit 4; }
SUMMARY=$(echo "$RESPONSE" | jq -r '.choices[0].message.content // empty')
[[ -n "$SUMMARY" && "$SUMMARY" != "null" ]] || { echo "❌ Empty summary in API response."; exit 4; }

# Save summary
echo "$SUMMARY" > summary.txt
echo "✅ AI Summary generated."
