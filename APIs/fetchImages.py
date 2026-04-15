"""
fetchImages API

Purpose:
--------
Fetches all raw images for a specific job from S3. Only images stored under
the "raw/images/{company_name}/" directory are returned. Company name is
normalized using `safe_name` to match the S3 folder structure.

Behavior:
---------
- Retrieves job and company info from DynamoDB ('jobs' and 'companies' tables).
- Lists all image files in S3 under the company's raw/images folder.
- Returns a JSON response with a list of presigned URLs for the images.
- If no images exist, returns an empty array with numImages=0 (does NOT return 404).
- Handles errors such as missing jobId, missing job or company entries, and S3/DynamoDB failures.

API endpoint: https://<YOUR-AWS-API>/dev/jobs/{jobId}/images
Method: GET

API input:
{
    "pathParameters": {
        "jobId": str
    }
}

All API output scenarios:
------------------------
1. Success - Images Found:
    Status Code: 200
    Body: {
        "jobId": str,
        "companyId": str,
        "numImages": int,
        "images": [
            {
                "key": str,         # S3 object key
                "url": str          # Presigned URL valid for 1 hour
            },
            ...
        ]
    }
2. Success - No Images Found:
    Status Code: 200
    Body: {
        "jobId": str,
        "companyId": str,
        "numImages": 0,
        "images": []
    }
3. Error - Missing jobId:
    Status Code: 400
    Body: {
        "error": "Missing jobId",
        "numImages": 0,
        "images": []
    }
4. Error - Job Not Found:
    Status Code: 404
    Body: {
        "error": "Job {jobId} not found",
        "numImages": 0,
        "images": []
    }
5. Error - Company Not Found:
    Status Code: 404
    Body: {
        "error": "Company {companyId} not found",
        "numImages": 0,
        "images": []
    }
6. Error - Internal Server Error:
    Status Code: 500
    Body: {
        "error": str,           # Error message
        "numImages": 0,
        "images": []
    }

Requirements:
-------------
- Environment Variables:
    * S3_BUCKET : S3 bucket containing raw images
    * JOBS_TABLE : DynamoDB table name for jobs
    * COMPANIES_TABLE : DynamoDB table name for companies
- IAM Role Permissions:
    * s3:ListBucket on BUCKET
    * s3:GetObject on raw/images/*
    * dynamodb:GetItem on JOBS_TABLE and COMPANIES_TABLE
"""

import os
import json
import boto3

# ----------------------------
# AWS Setup
# ----------------------------
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
JOBS_TABLE = dynamodb.Table(os.environ.get("JOBS_TABLE", "jobs"))
COMPANIES_TABLE = dynamodb.Table(os.environ.get("COMPANIES_TABLE", "companies"))
BUCKET = os.environ.get("S3_BUCKET", "test-2-adspy")
PRESIGNED_URL_EXPIRATION = int(os.environ.get("PRESIGNED_URL_EXPIRATION", 3600))  # 1 hour

# ----------------------------
# Utility Functions
# ----------------------------
def safe_name(s: str) -> str:
    """Convert company name into safe S3 folder name."""
    return "".join(c if c.isalnum() or c in (" ", ".", "_", "-") else "_" for c in s).replace(" ", "_").lower()

def log(msg: str):
    print(msg)

# ----------------------------
# Lambda Handler
# ----------------------------
def lambda_handler(event, context):
    try:

        if not event or not isinstance(event, dict):
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Invalid or missing jobId",
                    "numImages": 0,
                    "images": [],
                    "message": "jobId is required in path parameters"
                })
            }

        # Extract pathParameters (API Gateway)
        path_params = event.get("pathParameters") or {}
        job_id = path_params.get("jobId") if isinstance(path_params, dict) else None
        
        if not job_id or not isinstance(job_id, str) or not job_id.strip():
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing jobId", "numImages": 0, "images": []})
            }

        # Fetch job from DynamoDB
        job_item = JOBS_TABLE.get_item(Key={"jobId": job_id}).get("Item")
        if not job_item:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": f"Job {job_id} not found", "numImages": 0, "images": []})
            }

        company_id = job_item.get("companyId")
        company_item = COMPANIES_TABLE.get_item(Key={"companyId": company_id}).get("Item")
        if not company_item:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": f"Company {company_id} not found", "numImages": 0, "images": []})
            }

        company_name = company_item.get("companyName", "").strip()
        safe_company = safe_name(company_name)
        prefix = f"raw/images/{safe_company}/"

        # List objects in S3
        paginator = s3.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=BUCKET, Prefix=prefix)

        images = []
        for page in page_iterator:
            for obj in page.get("Contents", []):
                key = obj["Key"]
                # Only include image files
                if key.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                    url = s3.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": BUCKET, "Key": key},
                        ExpiresIn=PRESIGNED_URL_EXPIRATION  # 1 hour
                    )
                    images.append({"key": key, "url": url})

        response_body = {
            "jobId": job_id,
            "companyId": company_id,
            "numImages": len(images),
            "images": images
        }

        return {"statusCode": 200, "body": json.dumps(response_body)}

    except Exception as e:
        log(f"[error] {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e), "numImages": 0, "images": []})
        }
