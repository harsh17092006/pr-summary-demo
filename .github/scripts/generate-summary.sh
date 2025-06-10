#!/bin/bash

# Exit on error, unset variable, or failed pipe
set -euo pipefail

# Debug: Print all executed commands
set -x

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

# Check if GROQ_API_KEY is set
if [[ -z "${GROQ_API_KEY:-}" ]]; then
  echo "❌ GROQ_API_KEY environment variable not set. Exiting."
  exit 3
fi

# Fetch complete git history for proper diff base
if ! git fetch --unshallow origin main 2>/dev/null; then
  git fetch origin main
fi

# Ensure origin/main exists
if ! git show-ref --verify --quiet refs/remotes/origin/main; then
  echo "❌ Remote branch origin/main not found after fetch. Exiting."
  exit 1
fi

# Find merge base and generate diff
if git merge-base origin/main HEAD &>/dev/null; then
  git diff origin/main...HEAD > pr_diff.txt
else
  echo "⚠️ No merge base found. Falling back to full diff."
  git diff > pr_diff.txt
fi

# Trim diff to 10,000 characters and escape as JSON string
DIFF=$(head -c 10000 pr_diff.txt | jq -Rs .)

# Prepare Groq request payload
read -r -d '' DATA <<EOF
{
  "model": "llama3-70b-8192",
  "messages": [
    {
      "role": "system",
      "content": "You are an expert AI that summarizes GitHub pull request diffs into clean, concise summaries for reviewers. Focus on what was changed inside the code or files, not on filenames."
    },
    {
      "role": "user",
      "content": $DIFF
    }
  ]
}
EOF

# Make request to Groq
RESPONSE=$(curl -s https://api.groq.com/openai/v1/chat/completions \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$DATA")

# Debug: Print API response
echo "Groq API Response: $RESPONSE"

# Extract and save AI-generated summary
SUMMARY=$(echo "$RESPONSE" | jq -r '.choices[0].message.content // empty')

if [[ -z "$SUMMARY" || "$SUMMARY" == "null" ]]; then
  echo "❌ Failed to extract summary from API response. Exiting."
  exit 4
fi

echo "$SUMMARY" > summary.txt

# Optional: print it out for debug
echo "✅ AI Summary:"
echo "$SUMMARY"
