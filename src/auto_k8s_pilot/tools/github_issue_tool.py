from typing import Type

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from auto_k8s_pilot.settings import Settings


class GitHubIssueInput(BaseModel):
    repo: str = Field(..., description="owner/repo")
    title: str = Field(..., description="Issue title")
    body: str = Field(..., description="Issue body in Markdown")


class GitHubIssueTool(BaseTool):
    name: str = "github_create_issue"
    description: str = "Create a GitHub issue in a given repository."
    args_schema: Type[BaseModel] = GitHubIssueInput

    def _run(self, repo: str, title: str, body: str) -> str:
        settings = Settings()
        token = settings.GITHUB_TOKEN
        if not token:
            return "ERROR: GITHUB_TOKEN is not set."
        url = f"https://api.github.com/repos/{repo}/issues"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        payload = {"title": title, "body": body}
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=10)
            r.raise_for_status()
            num = r.json().get("number")
            return f"Created issue #{num} in {repo}"
        except Exception as e:
            return f"ERROR: GitHub API failed ({e})."

