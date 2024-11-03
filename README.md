# secure-code-reviewer

This repository is a collection of Github Actions that collectively represent the code for the Secure Code Reviewer, a tool that helps you review code with an LLM hosted on AWS Bedrock. 

To use the Secure Code Reviewer, request access to the AWS Bedrock Claude 3.5 Sonnet model. Additionally, you will need to create a new GitHub Secret with the AWS credentials. In your repository, go to Settings -> Secrets -> Actions and create the following new secrets with the AWS credentials: 

secrets.AWS_REGION - The AWS region where the Bedrock model is hosted.
secrets.AWS_ROLE_ARN - The ARN of the AWS role to assume.

To create the AWS IAM role, first you need to create an identity provider in AWS:

# In AWS Console:
1. Go to IAM
2. Click "Identity providers" in left sidebar
3. Click "Add provider"
4. Select "OpenID Connect"
5. For Provider URL enter: https://token.actions.githubusercontent.com
6. For Audience enter: sts.amazonaws.com
7. Click "Add provider"

Then, you need to create an IAM role. It will need to have the following trust relationship:

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Federated": "arn:aws:iam::<YOUR_ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
            },
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Condition": {
                "StringLike": {
                    "token.actions.githubusercontent.com:sub": "repo:<YOUR_GITHUB_ORG>/*"
                }
            }
        }
    ]
}
```

and the following permissions policy:

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:ListFoundationModels"
            ],
            "Resource": "*"
        }
    ]
}
```

Take the ARN of the role and add it to the GitHub secret as secrets.AWS_ROLE_ARN.

## How the PR Reviewer works

The PR Reviewer is a GitHub Action that reviews the code in a PR and provides feedback on the code. It uses the Claude 3.5 Sonnet model hosted on AWS Bedrock to provide the review.

The PR Reviewer will review the code in the PR and provide feedback on the code. It will provide feedback on the code in the PR and in the code in the PR.