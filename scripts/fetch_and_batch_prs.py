import os
from github import Github

def fetch_all_prs(repo_name, token, batch_size=20):
    # Authenticate using the provided GitHub token
    g = Github(token)
    repo = g.get_repo(repo_name)
    all_prs = []
    page = 0

    while True:
        prs_batch = repo.get_pulls(state="open", sort="created", direction="desc").get_page(page)
        if not prs_batch:
            break
        all_prs.extend(prs_batch)
        page += 1

    print(f"Total open PRs fetched: {len(all_prs)}")

    # Batch PRs for context window management
    batches = [all_prs[i:i+batch_size] for i in range(0, len(all_prs), batch_size)]
    for idx, batch in enumerate(batches):
        print(f"\nBatch {idx + 1} (PRs {idx * batch_size + 1} to {idx * batch_size + len(batch)}):")
        for pr in batch:
            print(f"- PR #{pr.number}: {pr.title}")

if __name__ == "__main__":
    REPO_NAME = "harsh17092006/pr-summary-demo"
    GITHUB_TOKEN = os.getenv("GH_ACCESS_TOKEN")
    if not GITHUB_TOKEN:
        raise EnvironmentError("GH_ACCESS_TOKEN environment variable not set")

    fetch_all_prs(REPO_NAME, GITHUB_TOKEN, batch_size=20)
