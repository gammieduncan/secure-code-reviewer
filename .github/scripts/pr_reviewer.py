import os
import boto3
import json
import time
import random
import sys
from github import Github
from botocore.config import Config

def get_bedrock_client():
    print("Initializing Bedrock client...")
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

def get_claude_review(bedrock_client, prompt, max_retries=5, initial_backoff=1):
    for attempt in range(max_retries):
        try:
            print(f"Attempt {attempt + 1}/{max_retries} to get Claude review...")
            
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "temperature": 0.7,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            })
            
            print("Invoking Claude model...")
            try:
                response = bedrock_client.invoke_model(
                    modelId='anthropic.claude-3-sonnet-20240620-v1:0',
                    body=body
                )
            except Exception as e:
                if 'ThrottlingException' in str(e):
                    if attempt == max_retries - 1:
                        print(f"Failed after {max_retries} attempts due to throttling")
                        raise
                    
                    backoff_time = initial_backoff * (2 ** attempt) + random.uniform(0, 1)
                    print(f"Request throttled. Waiting {backoff_time:.2f} seconds before retry...")
                    time.sleep(backoff_time)
                    continue
                else:
                    print(f"Unexpected error during invoke_model: {str(e)}")
                    raise
            
            print("Parsing response...")
            response_body = json.loads(response['body'].read())
            try:
                # Updated to match new response format
                response_text = response_body['content'][0]['text']
                review_comments = json.loads(response_text)
                print(f"Successfully parsed {len(review_comments)} review comments")
                return review_comments
            except json.JSONDecodeError as e:
                print(f"Failed to parse response as JSON: {e}")
                print(f"Raw response content: {response_text[:200]}...")
                return [{"path": None, "line": None, "body": response_text}]
                
        except Exception as e:
            print(f"Unexpected error during attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                raise
            continue
    
    return None  # In case all retries fail

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
