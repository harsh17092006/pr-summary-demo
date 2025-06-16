import os
import requests
import time
import re
import sys

try:
    GH_TOKEN = os.environ['GH_TOKEN']
    GROQ_API_KEY = os.environ['GROQ_API_KEY']
    REPO = os.environ['GITHUB_REPOSITORY']
    PR_NUMBER = os.environ['PR_NUMBER']
except KeyError as e:
    print(f"Missing required environment variable: {e}")
    sys.exit(1)

pr_url = f"https://api.github.com/repos/{REPO}/pulls/{PR_NUMBER}"
headers = {
    "Authorization": f"token {GH_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}
files_url = f"https://api.github.com/repos/{REPO}/pulls/{PR_NUMBER}/files"

# Fetch all files with pagination
files = []
page = 1
while True:
    resp = requests.get(
        f"{files_url}?page={page}&per_page=100",
        headers=headers
    )
    if resp.status_code != 200:
        print(f"Failed to fetch files (HTTP {resp.status_code}): {resp.text}")
        sys.exit(1)
    paged_files = resp.json()
    if not paged_files:
        break
    files.extend(paged_files)
    if len(paged_files) < 100:
        break
    page += 1

print(f"Fetched {len(files)} files for summary")
MAX_PATCH_LEN = 12000
MAX_RETRIES = 10

def call_groq_api(prompt, filename):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama3-70b-8192",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that summarizes code changes in pull requests."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 4096,
        "temperature": 0.4
    }
    retries = 0
    while retries < MAX_RETRIES:
        response = requests.post(url, headers=headers, json=data)
        try:
            result = response.json()
        except Exception:
            result = {}
        if response.status_code == 200 and 'choices' in result:
            return result['choices'][0]['message']['content'].strip()
        elif response.status_code == 429 or (isinstance(result, dict) and result.get('error', {}).get('code') == 'rate_limit_exceeded'):
            wait_time = result.get('error', {}).get('retry_after')
            if not wait_time:
                msg = result.get('error', {}).get('message', '')
                match = re.search(r'try again in ([\d\.]+)s', msg)
                if match:
                    wait_time = float(match.group(1))
            if not wait_time:
                wait_time = 2 ** retries
            print(f"Groq API rate limit for {filename}: {result.get('error', {}).get('message', '')} -- retrying in {wait_time}s (attempt {retries+1}/{MAX_RETRIES})")
            time.sleep(float(wait_time))
            retries += 1
        else:
            print(f"Groq API error for {filename}: {result}")
            break
    return None

# In-memory RAG context
context_summaries = []

def retrieve_relevant_context(current_patch, top_k=3):
    # Simple: use last k summaries. For embedding similarity, integrate sentence-transformers.
    return "\n---\n".join(context_summaries[-top_k:]) if context_summaries else ""

combined_patch = ""
for file in files:
    filename = file['filename']
    patch = file.get('patch', '')
    if patch:
        if len(patch) > MAX_PATCH_LEN:
            print(f"Patch for {filename} is too long ({len(patch)} chars), truncating to {MAX_PATCH_LEN} chars.")
            patch = patch[:MAX_PATCH_LEN] + "\n[...diff truncated...]"
        file_patch = f"---\nFile: {filename}\n{patch}"
        
        # RAG: Retrieve recent context
        relevant_context = retrieve_relevant_context(file_patch)
        # Use the same detailed prompt as before
        prompt = (
            "You are an expert AI tasked with generating a highly detailed pull request description summarizing code changes in the provided git diff patch. "
            "Analyze the patch and produce a professional, structured summary focusing exclusively on substantive code changes, ignoring metadata (e.g., timestamps, commit messages) "
            "formatting, or stylistic changes (e.g., whitespace, comments, variable renaming unless functionally significant). If the patch includes multiple files, summarize each file "
            "clearly indicating the filename in a header (e.g., 'File: filename'). For each file, structure the summary with bullet points under the following sections:\n\n"
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
            "  - Differences between the previous code state (e.g., what was missing, limited, or problematic) and the current code state (e.g., what’s now enabled or improved).\n"
            "Keep the summary concise, clear, and tailored for technical reviewers. Use a neutral, professional tone and avoid speculative or vague language (e.g., instead of 'several', be precise—provide numbers or specifics). "
            "Use sub-bullets for clarity when describing nested changes or aligning purpose/impact with specific changes. If the patch is empty or lacks code changes, state 'No substantive code changes.'\n"
            "Below are example summaries to guide the format and depth:\n\n"
            "[Relevant previous summaries for context]:\n"
            f"{relevant_context}\n\n"
            "Here is the git diff patch to analyze:\n\n"
            f"{file_patch}"
        )
        ai_summary = call_groq_api(prompt, filename)
        if ai_summary:
            context_summaries.append(ai_summary)
        combined_patch += f"\n\n{file_patch}"

# Final combined prompt for all changes
relevant_context = retrieve_relevant_context(combined_patch)
final_prompt = (
    "You are an expert AI tasked with generating a highly detailed pull request description summarizing code changes in the provided git diff patch. "
    # ... (rest of your unchanged prompt, omitted here for brevity)
    "[Relevant previous summaries for context]:\n"
    f"{relevant_context}\n\n"
    "Here is the git diff patch to analyze:\n\n"
    f"{combined_patch}"
)
ai_summary = call_groq_api(final_prompt, "all_files_combined")
summary_text = ai_summary if ai_summary else "No code changes detected for AI summary."

patch = {
    "body": f"### AI-generated Summary of Code Changes\n\n{summary_text}\n\n---\n*This summary was generated by Groq Llama3-70B.*"
}
resp = requests.patch(pr_url, headers=headers, json=patch)
if resp.status_code not in [200, 201]:
    print(f"Failed to update PR description (HTTP {resp.status_code}): {resp.text}")
else:
    print("PR description updated with AI-generated summary.")
