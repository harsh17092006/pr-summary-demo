#!/bin/bash

DIFF=$(cat pr_diff.txt | head -c 10000 | jq -Rs .)

read -r -d '' DATA <<EOF
{
  "model": "llama3-70b-8192",
  "messages": [
    {
      "role": "system",
      "content": "You are an expert AI that summarizes GitHub pull request diffs into clean, concise summaries for reviewers."
    },
    {
      "role": "user",
      "content": $DIFF
    }
  ]
}
EOF

RESPONSE=$(curl -s https://api.groq.com/openai/v1/chat/completions \
  -H "Authorization: Bearer $GROQ_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$DATA")

echo "$RESPONSE" | jq -r '.choices[0].message.content' > summary.txt
