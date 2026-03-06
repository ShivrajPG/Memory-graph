import os
import requests
import json

from dotenv import load_dotenv

load_dotenv() 
Github_Token = os.getenv("GITHUB_TOKEN")

Repo_Owner= "langchain-ai"
Repo_Name= "langchain"
Issues_To_Fetch = 30 

def fetching_issues(owner, repo, limit=10):
    """Fetches issues and their comments from a public GitHub repository."""
    
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"

    headers = { "Accept": "application/vnd.github.v3+json" , "Authorization": f"token {Github_Token}" }
    params = { "state": "all" , "per_page": limit }
    
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
        
        comments_url = issue['comments_url']  #the unstructured chat
        comments_response = requests.get(comments_url, headers=headers)
        comments_data = comments_response.json() if comments_response.status_code == 200 else []
        
        comments_formatted =[]   #to structured list
        for c in comments_data:
            comments_formatted.append({ "comment_id": str(c['id']),"user": c['user']['login'],"body": c['body'],"created_at": c['created_at']})
            
        artifact = { "source_id": f"github_issue_{issue_number}", "url": issue['html_url'], "title": issue['title'], "body": issue['body'], "state": issue['state'], "author": issue['user']['login'],"created_at": issue['created_at'], "comments": comments_formatted }
        
        corpus.append(artifact)
        
    return corpus

if __name__ == "__main__":
    data = fetching_issues(Repo_Owner, Repo_Name, limit=Issues_To_Fetch)
    
    with open("corpus.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        
    print(f"\n Successfully Saved {len(data)} issues to corpus.json!")
    
