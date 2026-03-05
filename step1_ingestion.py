import os
import requests
import json

from dotenv import load_dotenv

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

REPO_OWNER = "langchain-ai"
REPO_NAME = "langchain"
ISSUES_TO_FETCH = 30  # Started small for testing and fast iteration

def fetch_issues(owner, repo, limit=10):
    """Fetches issues and their comments from a public GitHub repository."""
    
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {GITHUB_TOKEN}"
    }
    params = {
        "state": "all",  # Get both open and closed issues
        "per_page": limit
    }
    
    print(f"Fetching {limit} issues from {owner}/{repo}...")
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code != 200:
        print(f"Error fetching issues: {response.text}")
        return []
        
    issues = response.json()
    corpus =[]
    
    for issue in issues:
        issue_number = issue['number']
        print(f"Fetching comments for issue #{issue_number}...")
        
        comments_url = issue['comments_url']
        comments_response = requests.get(comments_url, headers=headers)
        comments_data = comments_response.json() if comments_response.status_code == 200 else []
        
        comments_formatted =[]
        for c in comments_data:
            comments_formatted.append({
                "comment_id": str(c['id']),
                "user": c['user']['login'],
                "body": c['body'],
                "created_at": c['created_at']
            })
            
        artifact = {
            "source_id": f"github_issue_{issue_number}",
            "url": issue['html_url'],
            "title": issue['title'],
            "body": issue['body'],
            "state": issue['state'],
            "author": issue['user']['login'],
            "created_at": issue['created_at'],
            "comments": comments_formatted
        }
        
        corpus.append(artifact)
        
    return corpus

if __name__ == "__main__":
    data = fetch_issues(REPO_OWNER, REPO_NAME, limit=ISSUES_TO_FETCH)
    
    with open("corpus.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        
    print(f"\n Successfully Saved {len(data)} issues to corpus.json!")
