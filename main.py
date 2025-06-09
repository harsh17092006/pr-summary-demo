import os
import httpx
from fastapi import FastAPI, Request
from pydantic import BaseModel
from dotenv import load_dotenv
from ai_summarizer.groq_summarizer import GroqSummarizer
import traceback

print("Starting FastAPI app - main.py loaded")

# Load environment variables from .env
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise EnvironmentError("GITHUB_TOKEN is not set in the environment variables.")

app = FastAPI()
summarizer = GroqSummarizer()

class DiffInput(BaseModel):
    diff: str

@app.get("/")
def read_root():
    return {"message": "PR Summarizer API is running!"}

@app.post("/summarize")
async def summarize_diff(data: DiffInput):
    try:
        print("Incoming diff:", data.diff[:300])  # Print only preview for logs
        summary = await summarizer.summarize(data.diff)
        print("Generated summary:", summary)
        return {"summary": summary}
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}

@app.post("/webhook")
async def handle_webhook(request: Request):
    try:
        payload = await request.json()

        # Only respond to pull request creation events (new PR opened)
        if "pull_request" not in payload:
            print("Webhook event ignored: Not a pull request event")
            return {"message": "Ignored"}

        if payload.get("action") != "opened":
            print(f"Webhook event ignored: PR action is '{payload.get('action')}', not 'opened'")
            return {"message": "Ignored - Not a new PR"}

        pr = payload["pull_request"]
        pr_url = pr["url"]               # API URL to PATCH PR data
        files_url = pr_url + "/files"    # API URL to get changed files

        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json"
        }

        full_code_summary_input = ""

        async with httpx.AsyncClient() as client:
            # Step 1: Get list of changed files
            files_resp = await client.get(files_url, headers=headers)
            if files_resp.status_code != 200:
                print("Failed to fetch file list")
                return {"error": f"Failed to get file list: {files_resp.text}"}

            files_data = files_resp.json()

            # Step 2: Fetch raw content of each file
            for file in files_data:
                filename = file["filename"]
                raw_url = file.get("raw_url")

                if raw_url:
                    raw_resp = await client.get(raw_url, follow_redirects=True)
                    if raw_resp.status_code == 200:
                        file_content = raw_resp.text
                        full_code_summary_input += f"\n\n### {filename}\n{file_content}"
                    else:
                        print(f"Failed to fetch {filename}, status: {raw_resp.status_code}")

            if not full_code_summary_input.strip():
                return {"message": "No file contents found to summarize."}

            # Step 3: Summarize full file contents
            summary = await summarizer.summarize(
                f"This is the updated content of files changed in the PR:\n{full_code_summary_input}\n\nGenerate a summary of what each file or function is doing."
            )
            print("Generated summary:", summary)

            # Step 4: Append AI summary to existing PR description
            current_body = pr.get("body") or ""
            if "🧠 **AI Summary of PR File Contents**" in current_body:
                print("Summary already present in PR description. Skipping update.")
                return {"message": "Summary already present in PR description."}

            updated_body = current_body + "\n\n🧠 **AI Summary of PR File Contents**:\n\n" + summary

            # Step 5: PATCH the PR to update its description (body)
            update_resp = await client.patch(
                pr_url,
                headers=headers,
                json={"body": updated_body}
            )

            print("PR update response status:", update_resp.status_code)
            print("PR update response content:", update_resp.text)

            if update_resp.status_code != 200:
                return {
                    "error": f"Failed to update PR description. Status: {update_resp.status_code}, Response: {update_resp.text}"
                }

            return {"message": "PR description updated with AI summary successfully"}

    except Exception as e:
        traceback.print_exc()
        return {"error": str(e)}
