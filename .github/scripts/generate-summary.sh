#!/bin/bash

set -euo pipefail
set -x

# Clean up temporary files on exit
trap 'rm -f pr_diff.txt summary.txt response_debug.txt' EXIT

# Ensure jq is installed
if ! command -v jq &>/dev/null; then
  echo "❌ jq is required but not installed. Exiting."
  exit 2
fi

# Ensure gh is installed
if ! command -v gh &>/dev/null; then
  echo "❌ gh is required but not installed. Exiting."
  exit 2
fi

# Check if GROQ_API_KEY is set and valid
if [[ -z "${GROQ_API_KEY:-}" || "${#GROQ_API_KEY}" -lt 10 ]]; then
  echo "❌ GROQ_API_KEY is missing or appears invalid. Exiting."
  exit 3
fi

# Determine default branch
DEFAULT_BRANCH=$(git remote show origin | grep "HEAD branch" | awk '{print $NF}')
if [[ -z "$DEFAULT_BRANCH" ]]; then
  echo "❌ Could not determine default branch. Exiting."
  exit 1
fi

# Fetch default branch
if git rev-parse --is-shallow-repository &>/dev/null; then
  echo "ℹ️ Shallow repository detected, attempting unshallow fetch."
  git fetch --unshallow origin "$DEFAULT_BRANCH" || { echo "❌ Failed to fetch origin/$DEFAULT_BRANCH. Exiting."; exit 1; }
else
  git fetch origin "$DEFAULT_BRANCH" || { echo "❌ Failed to fetch origin/$DEFAULT_BRANCH. Exiting."; exit 1; }
fi

# Check if origin/$DEFAULT_BRANCH exists
if ! git show-ref --verify --quiet refs/remotes/origin/"$DEFAULT_BRANCH"; then
  echo "❌ Remote branch origin/$DEFAULT_BRANCH not found after fetch. Exiting."
  exit 1
fi

# Find merge base and generate diff
if git merge-base origin/"$DEFAULT_BRANCH" HEAD &>/dev/null; then
  git diff origin/"$DEFAULT_BRANCH"...HEAD > pr_diff.txt || { echo "❌ Failed to generate diff. Exiting."; exit 1; }
else
  echo "⚠️ No merge base found. Generating full diff instead."
  git diff > pr_diff.txt || { echo "❌ Failed to generate full diff. Exiting."; exit 1; }
fi

# Ensure pr_diff.txt is not empty
if [[ ! -s pr_diff.txt ]]; then
  echo "❌ pr_diff.txt is empty or missing. Exiting."
  exit 5
fi

# Process diff with truncation by lines
if [[ $(wc -l < pr_diff.txt) -gt 1000 ]]; then
  echo "⚠️ Diff exceeds 1,000 lines; truncating."
  DIFF=$(head -n 1000 pr_diff.txt | iconv -c -t utf-8)
else
  DIFF=$(iconv -c -t utf-8 < pr_diff.txt)
fi

if [[ -z "$DIFF" ]]; then
  echo "❌ iconv produced empty output. Exiting."
  exit 6
fi

# Convert diff to JSON
if ! DIFF_JSON=$(echo "$DIFF" | jq -Rs .); then
  echo "❌ Error while processing diff content with jq. Exiting."
  exit 6
fi

# Prepare Groq request payload
MODEL="${GROQ_MODEL:-llama3-70b-8192}"
DATA=$(jq -n \
  --arg model "$MODEL" \
  --arg diff "$DIFF" \
  '{
    "model": $model,
    "messages": [
      {
        "role": "system",
        "content": "You are an expert AI that summarizes GitHub pull request diffs into clean, concise summaries for reviewers. Focus on what was changed inside the code or files, not on filenames."
      },
      {
        "role": "user",
        "content": $diff
      }
    ]
  }')

# Make request to Groq
RESPONSE=$(curl -s -w "%{http_code}" https://api.groq.com/openai/v1/chat/completions \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$DATA" -o response_body.txt)
if [[ "$RESPONSE" != "200" ]]; then
  echo "❌ Groq API request failed with status $RESPONSE. Response: $(cat response_body.txt)"
  exit 4
fi
RESPONSE=$(cat response_body.txt)

# Debug: Save API response
echo "Groq API Response written to response_debug.txt"
echo "$RESPONSE" > response_debug.txt

# Extract and save AI-generated summary
if ! echo "$RESPONSE" | jq -e '.choices[0].message.content' >/dev/null; then
  echo "❌ Invalid or missing content in API response: $RESPONSE"
  exit 4
fi
SUMMARY=$(echo "$RESPONSE" | jq -r '.choices[0].message.content // empty')

if [[ -z "$SUMMARY" || "$SUMMARY" == "null" ]]; then
  echo "❌ Failed to extract summary from API response. Exiting."
  exit 4
fi

echo "$SUMMARY" > summary.txt
echo "✅ AI Summary:"
echo "$SUMMARY"
