import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

class GitHubUnconfiguredError(Exception):
    """Raised when GitHub integration is inherently unconfigured."""
    pass

class GitHubAPIError(Exception):
    """Raised when the GitHub API request fails or returns non-201."""
    pass

def get_github_status() -> dict:
    """
    Checks whether GitHub integration has the required environment variables.
    Requires GITHUB_TOKEN to be non-empty and GITHUB_REPO to match owner/repo format.
    """
    token = os.getenv("GITHUB_TOKEN", "").strip()
    repo = os.getenv("GITHUB_REPO", "").strip()
    
    if not token or token == "your-key-here":
        return {"configured": False}
        
    if not repo or repo == "your-key-here":
        return {"configured": False}
        
    # Validate format owner/repo
    if not re.match(r'^[\w.-]+/[\w.-]+$', repo):
        return {"configured": False}
        
    return {"configured": True}

def create_github_issue(title: str, body: str) -> dict:
    """
    Creates an issue on the configured GitHub repository.
    Raises GitHubUnconfiguredError immediately if not configured.
    Raises GitHubAPIError if the API call fails or returns non-201.
    """
    status = get_github_status()
    if not status["configured"]:
        raise GitHubUnconfiguredError("GitHub integration is not properly configured.")
        
    token = os.getenv("GITHUB_TOKEN").strip()
    repo = os.getenv("GITHUB_REPO").strip()
    
    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }
    payload = {
        "title": title,
        "body": body,
        "labels": ["ai-reliability-engineer", "auto-generated"]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10.0)
    except requests.RequestException as e:
        raise GitHubAPIError(f"Connection error to GitHub API: {str(e)}")
        
    if response.status_code != 201:
        error_msg = f"failed with status {response.status_code}"
        try:
            error_json = response.json()
            if "message" in error_json:
                error_msg += f": {error_json['message']}"
        except Exception:
            error_msg += f": {response.text[:200]}"
        raise GitHubAPIError(f"GitHub API {error_msg}")
        
    data = response.json()
    return {
        "issue_number": data.get("number"),
        "issue_url": data.get("html_url")
    }
