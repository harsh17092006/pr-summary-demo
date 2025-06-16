import os
import requests
from github import Github

REPO_NAME = os.getenv("GITHUB_REPOSITORY", "harsh17092006/pr-summary-demo")
GITHUB_TOKEN = os.getenv("GH_ACCESS_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
BATCH_SIZE = 20

# --- Your full detailed prompt here ---
def get_batch_prompt(prs_text):
    return (
        "You are an expert AI tasked with generating a highly detailed pull request description summarizing code changes. "
        "Analyze the following PRs and produce a professional, structured summary focusing exclusively on substantive code changes, ignoring metadata (e.g., timestamps, commit messages), "
        "formatting, or stylistic changes (e.g., whitespace, comments, variable renaming unless functionally significant). "
        "Clearly indicate the PR number and title in a header for each PR. Structure each PR summary with bullet points under the following sections:\n\n"
        "- **Changes**: Itemize every code change individually, including:\n"
        "  - Added, removed, or modified functions, sub-functions, methods, classes, variables, or logic blocks.\n"
        "  - For functions/methods: List the name, signature (parameters with types, return type), and describe the implementation (e.g., algorithm, key logic, sub-functions).\n"
        "    - Include sub-bullets for nested changes (e.g., helper functions, modified conditions, or inner loops).\n"
        "  - For variables: Specify type, scope, initialization, and purpose.\n"
        "  - For logic changes: Detail altered conditions, loops, or algorithms, including any nested logic.\n"
        "  - Use sub-bullets to describe sub-functions or nested changes within a single item.\n"
        "- **Purpose**: For each change listed, explain its specific intent, including:\n"
        "  - The problem solved, feature added, or improvement made (e.g., bug fix, new functionality).\n"
        "  - Context or motivation (e.g., user requirement, performance bottleneck).\n"
        "  - Use sub-bullets to align with each change in the 'Changes' section.\n"
        "- **Impact**: For each change listed, describe its expected effects on the codebase, including:\n"
        "  - New or altered functionality and its effect on user experience or system behavior.\n"
        "  - Performance implications (e.g., time complexity, memory usage, scalability).\n"
        "  - Affected modules, dependencies, APIs, or integration points.\n"
        "  - Maintainability or code organization improvements.\n"
        "  - Use sub-bullets to align with each change in the 'Changes' section.\n"
        "- **Overall Summary**: Summarize the collective purpose and impact of all changes, including:\n"
        "  - The overall goal of the changes (e.g., new feature, performance optimization).\n"
        "  - The combined effect on the codebase (e.g., enhanced functionality, improved performance).\n"
        "  - Differences between the previous code state (e.g., what was missing, limited, or problematic) and the current code state (e.g., what’s now enabled or improved).\n\n"
        "Here are the PRs to analyze:\n\n"
        f"{prs_text}"
    )

# --- The summarizer prompt for summaries of summaries ---
def get_meta_summary_prompt(batch_summaries_text):
    return (
        "You are an expert technical writer. Given the following detailed summaries of batches of pull requests, "
        "write a single cohesive and concise summary that captures the overall changes, themes, and impacts across all batches. "
        "Focus on main additions, removals, refactors, and system-wide effects. Use bullet points and an overall summary paragraph at the end.\n\n"
        f"{batch_summaries_text}"
    )

def ai_summarize(prompt, model="llama3-70b-8192"):
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that summarizes code changes in pull requests."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 4096,
            "temperature": 0.4
        }
    )
    return response.json()['choices'][0]['message']['content'].strip()

def main():
    if not GITHUB_TOKEN or not GROQ_API_KEY:
        raise EnvironmentError("Both GH_ACCESS_TOKEN and GROQ_API_KEY must be set!")
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)
    all_prs = []
    page = 0
    while True:
        prs_batch = repo.get_pulls(state="open", sort="created", direction="desc").get_page(page)
        if not prs_batch:
            break
        all_prs.extend(prs_batch)
        page += 1

    batches = [all_prs[i:i+BATCH_SIZE] for i in range(0, len(all_prs), BATCH_SIZE)]

    batch_summaries = []
    for idx, batch in enumerate(batches):
        # Gather all PRs' patch or diff text and titles for the batch
        batch_prs_text = ""
        for pr in batch:
            files = pr.get_files()
            for f in files:
                patch = getattr(f, "patch", "")
                if patch:
                    batch_prs_text += f"---\nPR #{pr.number}: {pr.title}\nFile: {f.filename}\n{patch}\n\n"
        prompt = get_batch_prompt(batch_prs_text)
        summary = ai_summarize(prompt)
        batch_summaries.append(f"**Batch {idx+1} Summary:**\n{summary}")

    # Now summarize the summaries
    meta_prompt = get_meta_summary_prompt("\n\n".join(batch_summaries))
    overall_summary = ai_summarize(meta_prompt)

    # Output to file for workflow step to use
    with open("combined_pr_summary.md", "w") as f:
        f.write(f"### AI-generated Overall Summary of All Open PRs\n\n{overall_summary}\n\n---\n\n")
        for batch_summary in batch_summaries:
            f.write(batch_summary + "\n\n")
    print("Summary written to combined_pr_summary.md")

if __name__ == "__main__":
    main()
