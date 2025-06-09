import os
import requests
import json
from openai import OpenAI

class AIOperations:
    def __init__(self, provider="xai", api_key=None, base_url="https://api.x.ai/v1"):
        """Initialize AI operations with a provider (xai or openai)."""
        self.provider = provider
        self.api_key = api_key or os.getenv("XAI_API_KEY")
        self.base_url = base_url
        self.client = self._initialize_client()

    def _initialize_client(self):
        """Initialize the AI client based on the provider."""
        if self.provider == "xai":
            return OpenAI(api_key=self.api_key, base_url=self.base_url)
        elif self.provider == "openai":
            return OpenAI(api_key=self.api_key)  # OpenAI uses default base_url
        else:
            raise ValueError(f"Unsupported AI provider: {self.provider}")

    def generate_summary(self, prompt, model="grok-beta", max_tokens=500):
        """Generate a summary using the AI provider's API."""
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert at summarizing technical changes concisely."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"Error generating summary: {str(e)}"

def get_pr_commits(owner, repo, pr_number, token):
    """Fetch commits in the PR."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/commits"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def get_pr_files(owner, repo, pr_number, token):
    """Fetch changed files in the PR."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def create_prompt(commits, files):
    """Create a prompt for the AI to summarize the PR."""
    commit_summary = "\n".join([f"- {commit['commit']['message']}" for commit in commits])
    file_summary = "\n".join([f"- {file['filename']} ({file['status']})" for file in files])
    return f"""Summarize the following pull request changes in a concise, professional manner, suitable for a PR description. Highlight key changes and their purpose.

### Commits:
{commit_summary}

### Changed Files:
{file_summary}

Provide a summary in markdown format with a heading 'PR Summary' and bullet points for key changes."""

def update_pr_description(owner, repo, pr_number, token, summary):
    """Update the PR description with the generated summary."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    data = {"body": summary}
    response = requests.patch(url, headers=headers, json=data)
    response.raise_for_status()

def main():
    owner = os.environ["GITHUB_REPOSITORY_OWNER"]
    repo = os.environ["GITHUB_REPOSITORY"].split("/")[-1]
    pr_number = os.environ["PR_NUMBER"]
    token = os.environ["GITHUB_TOKEN"]

    # Fetch PR details
    commits = get_pr_commits(owner, repo, pr_number, token)
    files = get_pr_files(owner, repo, pr_number, token)

    # Create prompt and generate summary
    prompt = create_prompt(commits, files)
    ai_ops = AIOperations(provider="xai")
    summary = ai_ops.generate_summary(prompt)

    # Update PR description
    update_pr_description(owner, repo, pr_number, token, summary)

if __name__ == "__main__":
    main()
