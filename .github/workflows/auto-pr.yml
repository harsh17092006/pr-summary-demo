name: Auto PR Summary with Grok AI

on:
  pull_request:
    types: [opened, reopened]

jobs:
  generate-pr-summary:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    env:
      PR_NUMBER: ${{ github.event.pull_request.number }}
      GITHUB_TOKEN: ${{ secrets.PAT_TOKEN }}
      XAI_API_KEY: ${{ secrets.XAI_API_KEY }}
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests openai

      - name: Run PR summary generator
        run: python generate_pr_summary.py
