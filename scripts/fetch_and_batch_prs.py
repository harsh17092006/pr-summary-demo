import os
import requests
from github import Github

REPO_NAME = "harsh17092006/pr-summary-demo"
GITHUB_TOKEN = os.getenv("GH_ACCESS_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
BATCH_SIZE = 20

def get_all_open_prs(repo):
    all_prs = []
    page = 0
    while True:
        prs_batch = repo.get_pulls(state="open", sort="created", direction="desc").get_page(page)
        if not prs_batch:
            break
        all_prs.extend(prs_batch)
        page += 1
    return all_prs

def ai_summarize(text, model="llama3-70b-8192"):
    if not text.strip():
        return "No PRs to summarize in this batch."
    prompt = (
        "You are an expert AI that summarizes pull request batches for technical reviewers. "
        "Summarize the following PRs, focusing on main changes, purposes, and impacts. "
        "Skip non-code changes. Be concise, structured, and professional.\n\n"
        f"{text}"
    )
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that summarizes pull requests in batches."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 1024,
            "temperature": 0.4
        }
    )
    return response.json()['choices'][0]['message']['content'].strip()

def main():
    if not GITHUB_TOKEN or not GROQ_API_KEY:
        raise EnvironmentError("Both GH_ACCESS_TOKEN and GROQ_API_KEY must be set!")
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    all_prs = get_all_open_prs(repo)
    batches = [all_prs[i:i+BATCH_SIZE] for i in range(0, len(all_prs), BATCH_SIZE)]

    batch_summaries = []
    for idx, batch in enumerate(batches):
        pr_lines = []
        for pr in batch:
            pr_lines.append(f"PR #{pr.number}: {pr.title}\n{pr.body or ''}\n")
        batch_text = "\n".join(pr_lines)
        summary = ai_summarize(batch_text)
        batch_summaries.append(f"**Batch {idx+1} Summary:**\n{summary}")

    # Combined summary
    combined_prompt = "\n\n".join(batch_summaries)
    combined_summary = ai_summarize(combined_prompt)

    with open("combined_pr_summary.md", "w") as f:
        f.write(f"### AI-generated Combined Summary of All Open PRs\n\n{combined_summary}\n\n---\n\n")
        for batch_summary in batch_summaries:
            f.write(batch_summary + "\n\n")

    # Print for workflow logs/debugging
    print(f"### AI-generated Combined Summary of All Open PRs\n\n{combined_summary}\n\n---\n")
    for batch_summary in batch_summaries:
        print(batch_summary + "\n")

if __name__ == "__main__":
    main()
