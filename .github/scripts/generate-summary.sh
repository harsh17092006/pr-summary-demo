#!/bin/bash

# Exit on error and show commands
set -euo pipefail

# STEP 1: Fetch complete git history for proper diff base
git fetch --unshallow origin main || git fetch origin main

# STEP 2: Check for a merge base between origin/main and HEAD
if git merge-base origin/main HEAD &>/dev/null; then
  git diff origin/main...HEAD > pr_diff.txt
else
  echo "⚠️ No merge base found. Falling back to full diff."
  git diff > pr_diff.txt
fi

# STEP 3: Trim diff to 10,000 characters and escape it as JSON string
if ! command -v jq &>/dev/null; then
  echo "jq is required but not installed. Exiting."
  exit 2
fi

DIFF=$(head -c 10000 pr_diff.txt | jq -Rs .)

# STEP 4: Prepare Groq request payload
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

# STEP 5: Make request to Groq
if [[ -z "${GROQ_API_KEY:-}" ]]; then
  echo "GROQ_API_KEY environment variable not set. Exiting."
  exit 3
fi

RESPONSE=$(curl -s https://api.groq.com/openai/v1/chat/completions \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$DATA")

# STEP 6: Extract and save AI-generated summary
SUMMARY=$(echo "$RESPONSE" | jq -r '.choices[0].message.content')
echo "$SUMMARY" > summary.txt

# Optional: print it out for debug
echo "✅ AI Summary:"
echo "$SUMMARY"
