"""
fetchReport API

Purpose:
--------
- Returns a presigned URL for an already-generated report.
- Does NOT trigger report generation; only provides download access.

Behavior:
---------
- Checks if the job exists in the jobs table.
- Checks if reportPath exists for the job.
- Returns presigned URL if report exists.
- Handles various states: missing jobId, job not found, report in progress, failed, or not yet generated.

API Endpoint: https://<YOUR-AWS-API>/dev/jobs/{jobId}/report
Method: GET

API Input:
----------
{
    "pathParameters": {
        "jobId": str   # Unique job identifier
    }
}

All API Output Scenarios:
------------------------
1. Success - Report Found:
    Status Code: 200
    Body:
    {
        "reportUrl": str,        # Presigned URL valid for 1 hour
        "reportPath": str,       # S3 object key
        "companyName": str,      # Name of the company associated with the report
        "expiresIn": int,        # URL expiration in seconds
        "message": "Report URL generated successfully"
    }

2. Error - Missing or Invalid jobId:
    Status Code: 400
    Body:
    {
        "error": "Invalid or missing jobId",
        "message": "jobId is required in path parameters"
    }

3. Error - Job Not Found:
    Status Code: 404
    Body:
    {
        "error": "Job not found",
        "message": "No job exists with ID {jobId}"
    }

4. Error - Report Not Found (reportPath empty and reportStatus = 0):
    Status Code: 404
    Body:
    {
        "error": "Report not found",
        "message": "No report has been generated for this job yet",
        "reportStatus": 0
    }

5. Error - Report Generation In Progress (reportStatus = 1):
    Status Code: 200
    Body:
    {
        "error": "Report not ready",
        "message": "Report is still being generated - please wait",
        "reportStatus": 1
    }

6. Error - Report Generation Failed (reportStatus = -1):
    Status Code: 200
    Body:
    {
        "error": "Report generation failed",
        "message": "Report generation permanently failed for this job",
        "reportStatus": -1
    }

7. Error - Internal Server Error / DynamoDB or S3 failures:
    Status Code: 500
    Body:
    {
        "error": "Internal server error",
        "message": str    # Detailed error message
    }

Notes:
------
- URL expiration is controlled by REPORT_URL_EXPIRATION environment variable (default 3600 seconds).
- Presigned URL is only generated if reportPath exists in DynamoDB.
"""

import os
import json
import boto3
import logging
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BUCKET = os.environ.get("S3_BUCKET", "test2")
JOBS_TABLE_NAME = os.environ.get("JOBS_TABLE", "jobs")
URL_EXPIRATION = int(os.environ.get("REPORT_URL_EXPIRATION", "3600"))  # 1 hour

dynamodb = boto3.resource('dynamodb')
jobs_table = dynamodb.Table(JOBS_TABLE_NAME)
s3 = boto3.client('s3')

def lambda_handler(event, context):
    """
    Generate presigned URL for existing report.
    
    Path: GET /report/{jobId}
    """
    try:

        if not event or not isinstance(event, dict):
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Invalid or missing jobId",
                    "message": "jobId is required in path parameters"
                })
            }

        path_params = event.get("pathParameters") or {}
        job_id = path_params.get("jobId") if isinstance(path_params, dict) else None
        if not job_id or not isinstance(job_id, str) or not job_id.strip():
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Invalid or missing jobId",
                    "message": "jobId is required in path parameters"
                })
            }
        
        # Fetch job
        try:
            response = jobs_table.get_item(Key={'jobId': job_id})
            job_item = response.get('Item')
        except Exception as e:
            logger.error(f"[dynamodb] Error fetching job {job_id}: {e}")
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": "Database error",
                    "message": f"Failed to retrieve job from database"
                })
            }
        
        if not job_item:
            return {
                "statusCode": 404,
                "body": json.dumps({
                    "error": "Job not found",
                    "message": f"No job exists with ID {job_id}"
                })
            }
        
        report_path = job_item.get('reportPath', '').strip()
        report_status = int(job_item.get('reportStatus', 0))

        company_name = job_item.get('companyName', 'Unknown Company')
        
        # Check if report exists
        if not report_path:
            if report_status == -1:
                return {
                    "statusCode": 200,
                    "body": json.dumps({
                        "error": "Report generation failed",
                        "message": "Report generation permanently failed for this job",
                        "reportStatus": -1
                    })
                }
            elif report_status == 1:
                return {
                    "statusCode": 200,
                    "body": json.dumps({
                        "error": "Report not ready",
                        "message": "Report is still being generated - please wait",
                        "reportStatus": 1
                    })
                }
            else:
                return {
                    "statusCode": 404,
                    "body": json.dumps({
                        "error": "Report not found",
                        "message": "No report has been generated for this job yet",
                        "reportStatus": 0
                    })
                }
        
        # Generate presigned URL
        try:
            url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': BUCKET, 'Key': report_path},
                ExpiresIn=URL_EXPIRATION
            )
            
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "reportUrl": url,
                    "reportPath": report_path,
                    "companyName": company_name,
                    "expiresIn": URL_EXPIRATION,
                    "message": "Report URL generated successfully"
                })
            }
            
        except Exception as e:
            logger.error(f"[s3] Failed to generate presigned URL for {report_path}: {e}")
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "error": "Failed to generate download URL",
                    "message": f"Report exists but failed to create download link: {str(e)}"
                })
            }
    
    except Exception as e:
        logger.exception(f"[error] Unhandled exception in fetchReport: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Internal server error",
                "message": f"Unexpected error: {str(e)}"
            })
        }