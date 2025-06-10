#!/bin/bash

# Exit on error
set -e

# STEP 1: Generate full PR diff and save to file
git fetch origin main
git diff origin/main...HEAD > pr_diff.txt

# STEP 2: Trim diff to 10,000 characters and escape it as JSON string
DIFF=$(head -c 10000 pr_diff.txt | jq -Rs .)

# STEP 3: Prepare Groq request payload
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

# STEP 4: Make request to Groq
RESPONSE=$(curl -s https://api.groq.com/openai/v1/chat/completions \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$DATA")

# STEP 5: Extract and save AI-generated summary
SUMMARY=$(echo "$RESPONSE" | jq -r '.choices[0].message.content')
echo "$SUMMARY" > summary.txt

# Optional: print it out for debug
echo "✅ AI Summary:"
echo "$SUMMARY"
