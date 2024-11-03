import os
import boto3
import json
from github import Github
from botocore.config import Config

def get_bedrock_client():
    config = Config(
        region_name=os.environ["AWS_REGION"]
    )
    return boto3.client(
        service_name='bedrock-runtime',
        config=config
    )

def get_pr_details(github_token, repo_name, pr_number):
    g = Github(github_token)
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    
    # Get PR description and diff
    files = pr.get_files()
    diff = "\n".join([f"File: {file.filename}\n{file.patch}" for file in files if file.patch])
    description = pr.title + "\n" + (pr.body or "")
    
    return pr, diff, description

def create_review_prompt(diff, description):
    return f"""Please review the following pull request changes:

PR Description:
{description}

Changes:
{diff}

Please analyze the changes and provide specific feedback on:
1. Does the PR accomplish what it sets out to accomplish based on the description?
2. Are there any potential errors or flaws in the implementation?
3. Could the code be organized in a better way?
4. Are there opportunities for performance improvements or better design patterns?

Format your response as a JSON array of review comments. Each comment should have these fields:
- path: the file path
- line: the line number to comment on (use null for general comments)
- body: the comment text

Example:
[
    {{"path": "src/main.py", "line": 45, "body": "Consider using a list comprehension here for better performance"}},
    {{"path": null, "line": null, "body": "Overall, the PR implements the feature well but could use some optimization"}}
]"""

def get_claude_review(bedrock_client, prompt):
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7
    })
    
    response = bedrock_client.invoke_model(
        modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
        body=body
    )
    
    response_body = json.loads(response['body'].read())
    try:
        review_comments = json.loads(response_body['messages'][0]['content'])
        return review_comments
    except json.JSONDecodeError:
        # Fallback if Claude doesn't return valid JSON
        return [{"path": None, "line": None, "body": response_body['messages'][0]['content']}]

def main():
    # Get environment variables
    github_token = os.environ["GITHUB_TOKEN"]
    repo_name = os.environ["GITHUB_REPOSITORY"]
    pr_number = int(os.environ["PR_NUMBER"])
    
    # Initialize clients
    bedrock_client = get_bedrock_client()
    
    # Get PR information
    pr, diff, description = get_pr_details(github_token, repo_name, pr_number)
    
    # Create and send prompt to Claude
    prompt = create_review_prompt(diff, description)
    review_comments = get_claude_review(bedrock_client, prompt)
    
    # Create a new review with comments
    comments = []
    general_comments = []
    
    for comment in review_comments:
        if comment["path"] and comment["line"]:
            comments.append({
                "path": comment["path"],
                "line": comment["line"],
                "body": comment["body"]
            })
        else:
            general_comments.append(comment["body"])
    
    # Submit the review
    if comments:
        pr.create_review(
            commit=pr.get_commits().reversed[0],
            comments=comments,
            body="\n\n".join(general_comments) if general_comments else None,
            event="COMMENT"
        )
    elif general_comments:
        pr.create_issue_comment("\n\n".join(general_comments))

if __name__ == "__main__":
    main()
