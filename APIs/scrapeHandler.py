"""
scrapeHandler API

Behavior Overview:
-----------------
This API handles job-based scraping requests for companies. It is designed to be polled
multiple times by the same job or multiple jobs running in parallel.
-----------------

API Endpoint: https://<YOUR-AWS-API>/dev/jobs/{jobId}/scraper-status
Method: GET

API input:

{
    "pathParameters": {
        "jobId": str
    }
}

All API output scenarios:

1. Success - Job Permanently Failed (Already Marked)
   Status Code: 200
   Response Body:
   {
       "scraperStatus": -1,
       "triggeredScrape": false,
       "scraperRetryCount": 3,
       "message": "Job has permanently failed"
   }

2. Success - Job Already Completed or Scraping Not Needed
   Status Code: 200
   Response Body:
   {
       "scraperStatus": 2,
       "triggeredScrape": false,
       "scraperRetryCount": 0,
       "message": "Job has already completed"
   }

3. Success - Job Waiting for Another Job to Finish (Company Already Being Scraped or Lock Race)
   Status Code: 200
   Response Body:
   {
       "scraperStatus": 1,
       "triggeredScrape": false,
       "message": "Job is waiting for another job to finish"
   }

4. Success - Scraping Completed Successfully
   Status Code: 200
   Response Body:
   {
       "scraperStatus": 2,
       "triggeredScrape": true,
       "scraperRetryCount": 0,
       "numAds": int,
       "message": "Scraping completed successfully"
   }

5. Success - Transient Error (Will Retry Later)
   Status Code: 200
   Response Body:
   {
       "scraperStatus": 0,
       "triggeredScrape": false,
       "retrying": true,
       "scraperRetryCount": int,
       "error": str
   }

6. Success - Permanent Scrape Error (Invalid Input or Unrecoverable Failure)
   Status Code: 200
   Response Body:
   {
       "scraperStatus": -1,
       "triggeredScrape": false,
       "scraperRetryCount": int,
       "permanent": true,
       "error": str
   }

7. Success - Max Retries Exceeded (Now Permanently Failed)
   Status Code: 200
   Response Body:
   {
       "scraperStatus": -1,
       "triggeredScrape": false,
       "scraperRetryCount": int,
       "permanent": true,
       "error": str
   }

8. Error - Invalid or Missing jobId
   Status Code: 400
   Response Body:
   {
       "error": "Invalid or missing jobId"
   }

9. Error - Job Not Found
   Status Code: 404
   Response Body:
   {
       "error": "Job not found"
   }

10. Error - Internal Server Error
    Status Code: 500
    Response Body:
    {
        "error": "Internal server error"
    }

Scenarios:

1. Single Job / Single Company:
   - Job scraperStatus = 0 (idle)
   - Company scraperStatus = 0 (idle)
   - API checks if scraping is needed:
       - If company never scraped, stale (older than 30 days), or numAds = 0:
           - Lock is acquired
           - Job and Company scraperStatus set to 1 (in progress)
           - Scraper runs
           - On completion, Job and Company scraperStatus set to 2 (completed)
       - If scraping not needed:
           - Job scraperStatus set to 2 immediately
           - API returns triggeredScrape = False

2. Multiple Jobs / Single Company (Simultaneous Polling):
   - JobA acquires lock first:
       - Sets JobA.scraperStatus = 1
       - Sets Company.scraperStatus = 1
   - JobB polls during JobA scraping:
       - Cannot acquire lock
       - JobB.scraperStatus set to 1 (reflects waiting for scrape)
       - API returns scraperStatus = 1, triggeredScrape = False
   - When JobA finishes scraping:
       - Updates Company.scraperStatus = 2
       - Updates JobA.scraperStatus = 2
       - Updates all other jobs tied to the company (JobB, etc.) scraperStatus = 2
   - Subsequent polls by JobB will see scraperStatus = 2 and triggeredScrape = False

3. Stale Job or Company:
   - If a job or company has scraperStatus = 1 for longer than SCRAPER_TIMEOUT_SECONDS, it is considered stale
   - Any subsequent job polling can acquire the lock to retry scraping

4. Retry logic:
   - Each job tracks a scraperRetryCount for failed scraping attempts
   - On scraper failure:
       - scraperRetryCount is incremented
       - If scraperRetryCount <= MAX_RETRIES:
           - Job scraperStatus reset to 0 (idle) so it can retry later
           - Company scraperStatus reset to 0 (idle) if necessary
       - If scraperRetryCount > MAX_RETRIES:
           - Job scraperStatus set to -1 (permanently failed)
           - Company scraperStatus is **not marked as permanently failed**, so it remains eligible for future scraping by other jobs
   - scraperRetryCount is reset to 0 when scraping succeeds or when no scraping is needed

Key Notes:
- No duplicate scraping occurs while still tracking scrape status per job
- Jobs tied to the same company are updated automatically to reflect completion
- Polling stops correctly because status 2 always reflects "scraping done," even if no actual scrape was needed
- Requires a GSI on jobs table for companyId to update all related jobs efficiently
"""

import os
import json
import boto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
from datetime import datetime, timezone, timedelta

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# -------------------------------
# Constants & DynamoDB Setup
# -------------------------------
dynamodb = boto3.resource('dynamodb')
jobs_table = dynamodb.Table("jobs")
companies_table = dynamodb.Table("companies")
dynamodb_client = boto3.client('dynamodb')

try:
    SCRAPER_TIMEOUT_SECONDS = int(os.environ.get("SCRAPER_TIMEOUT_SECONDS", "300"))
    logger.info(f"SCRAPER_TIMEOUT_SECONDS (type={type(SCRAPER_TIMEOUT_SECONDS)}): {SCRAPER_TIMEOUT_SECONDS}")
except (ValueError, TypeError):
    SCRAPER_TIMEOUT_SECONDS = 300

try:
    MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
    logger.info(f"MAX_RETRIES (type={type(MAX_RETRIES)}): {MAX_RETRIES}")
except (ValueError, TypeError):
    MAX_RETRIES = 3

try:
    SCRAPE_INTERVAL_DAYS = int(os.environ.get("SCRAPE_INTERVAL_DAYS", "30"))
    logger.info(f"SCRAPE_INTERVAL_DAYS (type={type(SCRAPE_INTERVAL_DAYS)}): {SCRAPE_INTERVAL_DAYS}")
except (ValueError, TypeError):
    SCRAPE_INTERVAL_DAYS = 15

#-------------------------------
# Lambda Invoke Setup
#-------------------------------
lambda_client = boto3.client('lambda')

# -------------------------------
# Utility Functions
# -------------------------------
def decimal_default(obj):
    """Convert Decimal to int for JSON serialization."""
    if isinstance(obj, Decimal):
        return int(obj)
    raise TypeError

def parse_iso_date(date_str: str):
    """Safely parse ISO datetime string. Return None if invalid."""
    try:
        return datetime.fromisoformat(date_str)
    except (TypeError, ValueError):
        return None

def is_stale(timestamp_str: str, timeout_seconds: int = SCRAPER_TIMEOUT_SECONDS) -> bool:
    """Check if a timestamp is considered stale (older than timeout)."""
    ts = parse_iso_date(timestamp_str)
    if not ts:
        return True
    return (datetime.now(timezone.utc) - ts) > timedelta(seconds=timeout_seconds)

def needs_scraping(company_item) -> bool:
    if not company_item:
        return True
    num_ads = int(company_item.get('numAds', 0))
    date_scraped_str = company_item.get('dateScraped')
    if num_ads == 0 or not date_scraped_str:
        return True
    date_scraped = parse_iso_date(date_scraped_str)
    if not date_scraped:
        return True
    return (datetime.now(timezone.utc) - date_scraped) >= timedelta(days=SCRAPE_INTERVAL_DAYS)

# -------------------------------
# Scraping Function
# -------------------------------
def scrape(company_id: str, job_id: str):
    """
    Calls the separate scraper Lambda to perform scraping.

    Parameters:
    - company_id: str
    - job_id: str

    Returns:
    - new_status: int (2 = scrape complete)
    - actual_num_ads: int
    """
    SCRAPER_LAMBDA_NAME = "scrape"
    payload = {"companyId": company_id, "jobId": job_id}
    try:
        response = lambda_client.invoke(
            FunctionName=SCRAPER_LAMBDA_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload)
        )
        if response.get('FunctionError'):
            error_message = response['Payload'].read().decode('utf-8')
            logger.error(f"Scraper Lambda failed: {error_message}")
            # Classify as permanent if the error indicates invalid input
            if "Invalid company name" in error_message:  # Adjust based on actual scraper Lambda error messages
                raise ValueError("Permanent error: Invalid company name")
            raise Exception(f"Transient error: Scraper Lambda failed with FunctionError")
        result_payload = response['Payload'].read().decode('utf-8')
        try:
            result = json.loads(result_payload)
        except json.JSONDecodeError:
            logger.error("Invalid JSON response from scraper Lambda")
            raise ValueError("Permanent error: Invalid JSON response from scraper Lambda")
        if 'status' not in result or 'numAds' not in result:
            logger.error("Missing status or numAds in scraper Lambda response")
            raise ValueError("Permanent error: Invalid response from scraper Lambda: missing status or numAds")
        new_status = int(result['status'])
        actual_num_ads = int(result['numAds'])
        return new_status, actual_num_ads
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code in ['ResourceNotFoundException', 'AccessDeniedException']:
            logger.error(f"Permanent AWS ClientError invoking scraper Lambda: {str(e)}")
            raise ValueError(f"Permanent error: {error_code}")
        logger.error(f"Transient AWS ClientError invoking scraper Lambda: {str(e)}")
        raise Exception(f"Transient error: {error_code}")
    except Exception as e:
        logger.error(f"Error invoking scraper Lambda: {str(e)}")
        raise

# -------------------------------
# DynamoDB Transaction Helpers
# -------------------------------
def lock_job_and_company(job_id: str, company_id: str, company_name: str,
                         company_item, is_job_stale: bool, is_company_stale: bool) -> bool:
    """
    Attempt to lock job and company atomically. Returns True if lock acquired.
    Sets scraperStatus = 1 for both job and company if lock succeeds.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    stale_time_iso = (datetime.now(timezone.utc) - timedelta(seconds=SCRAPER_TIMEOUT_SECONDS)).isoformat()
    transact_items = []

    # --- Job Lock ---
    # Lock conditions:
    # 1. Job doesn't exist yet (attribute_not_exists)
    # 2. Job is idle (scraperStatus = 0)
    # 3. Job is stale (scraperStatus = 1 AND scraperStartedAt is old)
    transact_items.append({
        'Update': {
            'TableName': "jobs",
            'Key': {'jobId': {'S': job_id}},
            'UpdateExpression': "SET scraperStatus = :newStatus, scraperStartedAt = :ts",
            'ConditionExpression': (
                "attribute_not_exists(scraperStatus) OR "
                "scraperStatus = :idleStatus OR "
                "(scraperStatus = :inProgressStatus AND scraperStartedAt < :staleTime)"
            ),
            'ExpressionAttributeValues': {
                ':newStatus': {'N': '1'},
                ':idleStatus': {'N': '0'},
                ':inProgressStatus': {'N': '1'},
                ':staleTime': {'S': stale_time_iso},
                ':ts': {'S': now_iso}
            }
        }
    })

    # --- Company Lock ---
    company_status = company_item.get('scraperStatus', 0) if company_item else 0
    
    # Case 1: Company doesn't exist - create it
    if not company_item:
        transact_items.append({
            'Put': {
                'TableName': "companies",
                'Item': {
                    'companyId': {'S': company_id},
                    'companyName': {'S': company_name},
                    'domain': {'S': ''},
                    'meta_query': {'S': ''},
                    'google_query': {'S': ''},
                    'reddit_query': {'S': ''},
                    'linkedin_query': {'S': ''},
                    'scraperStatus': {'N': '1'},
                    'numAds': {'N': '0'},
                    'dateScraped': {'NULL': True},
                    'scraperStartedAt': {'S': now_iso},
                    'image2textStatus': {'N': '0'}
                },
                'ConditionExpression': "attribute_not_exists(companyId)"
            }
        })
    # Case 2: Company exists and is either idle (0) or stale (1 but timed out)
    elif company_status == 0 or (company_status == 1 and is_company_stale):
        transact_items.append({
            'Update': {
                'TableName': "companies",
                'Key': {'companyId': {'S': company_id}},
                'UpdateExpression': "SET scraperStatus = :newStatus, scraperStartedAt = :ts",
                'ConditionExpression': (
                    "attribute_not_exists(scraperStatus) OR "
                    "scraperStatus = :idleStatus OR "
                    "(scraperStatus = :inProgressStatus AND scraperStartedAt < :staleTime)"
                ),
                'ExpressionAttributeValues': {
                    ':newStatus': {'N': '1'},
                    ':idleStatus': {'N': '0'},
                    ':inProgressStatus': {'N': '1'},
                    ':staleTime': {'S': stale_time_iso},
                    ':ts': {'S': now_iso}
                }
            }
        })
    # Case 3: Company is in progress and not stale - cannot lock
    else:
        return False

    if not transact_items:
        return False

    try:
        dynamodb_client.transact_write_items(TransactItems=transact_items)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == "TransactionCanceledException":
            return False
        raise

# -------------------------------
# Lambda Handler
# -------------------------------
def lambda_handler(event, context):
    try:
        # --- Validate Input ---
        job_id = event.get('pathParameters', {}).get('jobId')
        if not job_id or not isinstance(job_id, str) or not job_id.strip():
            return {"statusCode": 400, "body": json.dumps({"error": "Invalid or missing jobId"})}

        # --- Fetch Job ---
        response = jobs_table.get_item(Key={'jobId': job_id})
        job_item = response.get('Item')
        if not job_item:
            return {"statusCode": 404, "body": json.dumps({"error": "Job not found"})}

        scraper_status = int(job_item.get('scraperStatus', 0))
        
        if scraper_status == -1:
            # Job permanently failed, do not attempt to scrape again
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "scraperStatus": -1,
                    "triggeredScrape": False,
                    "scraperRetryCount": int(job_item.get('scraperRetryCount', 0)),
                    "message": "Job has permanently failed"
                }, default=decimal_default)
            }
        elif scraper_status == 2:
            # Job already completed, do not attempt to scrape again
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "scraperStatus": 2,
                    "triggeredScrape": False,
                    "scraperRetryCount": int(job_item.get('scraperRetryCount', 0)),
                    "message": "Job has already completed"
                }, default=decimal_default)
            }

        scraper_started_at_str = job_item.get('scraperStartedAt')
        company_name = str(job_item.get('companyName', '')).strip().lower()
        company_id = job_item.get('companyId')
        if not company_id or not isinstance(company_id, str) or not company_id.strip():
            return {"statusCode": 400, "body": json.dumps({"error": "Invalid or missing companyId in job"})}

        # --- Check Job Stale ---
        is_job_stale = scraper_status == 1 and is_stale(scraper_started_at_str)

        # --- Fetch Company ---
        company_item = companies_table.get_item(Key={'companyId': company_id}).get('Item')
        should_scrape = needs_scraping(company_item)

        # --- Reset Company Status if Re-scraping Needed ---
        if should_scrape and company_item and int(company_item.get('scraperStatus', 0)) == 2:
            try:
                companies_table.update_item(
                    Key={'companyId': company_id},
                    UpdateExpression="SET scraperStatus = :status",
                    ConditionExpression="scraperStatus = :expectedStatus",  # Only update if still 2
                    ExpressionAttributeValues={
                        ':status': 0,
                        ':expectedStatus': 2
                    }
                )
                logger.info(f"[reset] Company {company_id} needs re-scraping, reset status 2->0")
                company_item['scraperStatus'] = 0  # Update local copy
            except ClientError as e:
                if e.response['Error']['Code'] != 'ConditionalCheckFailedException':
                    logger.error(f"[reset] Failed to reset company status: {e}")

        # --- Check Company Stale ---
        company_scraper_started = company_item.get('scraperStartedAt') if company_item else None
        is_company_stale = company_item and company_item.get('scraperStatus') == 1 and is_stale(company_scraper_started)

        # --- Early Return: Nothing to scrape ---
        # Check if the company does NOT need scraping and neither the job nor the company is stale
        # This means:
        #   - should_scrape is False -> company already scraped recently (less than 30 days) and has numAds > 0
        #   - is_job_stale is False -> job isn't stuck in "in-progress" (scraperStatus=1) for too long
        #   - is_company_stale is False -> company isn't stuck in "in-progress" for too long
        # Note: This is one of the early exits; the job is marked completed if necessary.
        if not should_scrape and not is_job_stale and not is_company_stale:
            # If the job is not already marked as completed (scraperStatus=2)
            if scraper_status != 2:
                # Update the job in DynamoDB to mark it as completed
                # Also reset scraperRetryCount to 0 since scraping is not needed
                jobs_table.update_item(
                    Key={'jobId': job_id},
                    UpdateExpression="SET scraperStatus = :status, scraperRetryCount = :rc",
                    ExpressionAttributeValues={':status': 2, ':rc': 0}
                )
                scraper_status = 2  # Update local variable to reflect new status
            # Return immediately: scraping not triggered because it's unnecessary
            return {
                "statusCode": 200,
                "body": json.dumps({"scraperStatus": scraper_status, 
                                    "triggeredScrape": False,
                                    "message": "Job has already completed"
                                    }, default=decimal_default)
            }

        # --- Lock Job + Company ---
        # If the company exists AND its scraperStatus is 1 (in progress) AND it is NOT stale
        # This means another job is already actively scraping this company
        if company_item and company_item.get('scraperStatus') == 1 and not is_company_stale:
            # If the current job is not already marked as waiting (scraperStatus=1)
            if scraper_status != 1:
                # Update the job to reflect that it is waiting for the current scraping to finish
                jobs_table.update_item(
                    Key={'jobId': job_id},
                    UpdateExpression="SET scraperStatus = :status",
                    ExpressionAttributeValues={':status': 1}
                )
            # Return immediately: this job is waiting, so scraping not triggered
            # Note: This is the first "waiting" update. There is another later if lock acquisition fails.
            return {"statusCode": 200, "body": json.dumps({"scraperStatus": 1, 
                                                           "triggeredScrape": False,
                                                           "message": "Job is waiting for another job to finish"
                                                           }, default=decimal_default)}

        # Attempt to acquire an atomic lock on the job and company
        # Locking ensures only one job can scrape the company at a time
        locked = lock_job_and_company(job_id, company_id, company_name, company_item, is_job_stale, is_company_stale)

        # If the lock could NOT be acquired
        # Scenario: Race condition where another job acquired the lock just before this job tried
        # - At this point, company.scraperStatus might still be 0 (not yet marked in-progress)
        # - The job still needs to be marked as waiting to reflect that it will wait for the job that got the lock
        # Subsequent polls of this job will likely hit the first "waiting" block once company.scraperStatus is updated
        if not locked:
            # If the job is not already marked as waiting (scraperStatus=1)
            if scraper_status != 1:
                # Update job status to reflect waiting for the company scrape to finish
                jobs_table.update_item(
                    Key={'jobId': job_id},
                    UpdateExpression="SET scraperStatus = :status",
                    ExpressionAttributeValues={':status': 1}
                )
            # Return immediately: lock not acquired, so scraping not triggered
            # Note: This is the second "waiting" update; ensures jobs are correctly marked during lock race conditions
            return {"statusCode": 200, "body": json.dumps({"scraperStatus": 1,
                                                           "triggeredScrape": False,
                                                           "message": "Job is waiting for another job to finish"
                                                           }, default=decimal_default)}

        # --- Perform Scraping ---
        try:
            new_status, actual_num_ads = scrape(company_id, job_id)
        except ValueError as e:
            # Permanent error: mark job as permanently failed, unlock company,
            # but DO NOT raise — return 200 so frontend sees permanent failure state.
            retry_count = int(job_item.get('scraperRetryCount', 0)) + 1
            jobs_table.update_item(
                Key={'jobId': job_id},
                UpdateExpression="SET scraperStatus = :status, scraperRetryCount = :rc",
                ExpressionAttributeValues={':status': -1, ':rc': retry_count}
            )
            companies_table.update_item(
                Key={'companyId': company_id},
                UpdateExpression="SET scraperStatus = :status",
                ExpressionAttributeValues={':status': 0}
            )
            logger.error(f"Permanent scrape error for job {job_id}: {str(e)}")
            # Return a 200 so frontend can show a controlled permanent-failure state
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "scraperStatus": -1,
                    "triggeredScrape": False,
                    "scraperRetryCount": retry_count,
                    "permanent": True,
                    "error": str(e)
                }, default=decimal_default)
            }
        except Exception as e:
            # Transient error: increment scraperRetryCount and either schedule retry or mark failed.
            retry_count = int(job_item.get('scraperRetryCount', 0))

            if retry_count >= MAX_RETRIES:
                # Permanent failure without incrementing
                jobs_table.update_item(
                    Key={'jobId': job_id},
                    UpdateExpression="SET scraperStatus = :status, scraperRetryCount = :rc",
                    ExpressionAttributeValues={':status': -1, ':rc': retry_count}
                )
                companies_table.update_item(
                    Key={'companyId': company_id},
                    UpdateExpression="SET scraperStatus = :status",
                    ExpressionAttributeValues={':status': 0}
                )
                logger.error(f"Transient scrape error for job {job_id} (max retries exceeded): {str(e)}")
                return {
                    "statusCode": 200,
                    "body": json.dumps({
                        "scraperStatus": -1,
                        "triggeredScrape": False,
                        "scraperRetryCount": retry_count,
                        "permanent": True,
                        "error": str(e)
                    }, default=decimal_default)
                }
            else:
                # Increment retry_count and continue retry
                retry_count += 1
                jobs_table.update_item(
                    Key={'jobId': job_id},
                    UpdateExpression="SET scraperStatus = :status, scraperRetryCount = :rc",
                    ExpressionAttributeValues={':status': 0, ':rc': retry_count}
                )
                companies_table.update_item(
                    Key={'companyId': company_id},
                    UpdateExpression="SET scraperStatus = :status",
                    ExpressionAttributeValues={':status': 0}
                )
                logger.error(f"Transient scrape error for job {job_id} (will retry): {str(e)}")
                return {
                    "statusCode": 200,
                    "body": json.dumps({
                        "scraperStatus": 0,
                        "triggeredScrape": False,
                        "retrying": True,
                        "scraperRetryCount": retry_count,
                        "error": str(e)
                    }, default=decimal_default)
                }
        # --- Update Company with Scraped Data ---
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            # Set scraperStatus to 0 if numAds is 0, otherwise 2
            final_scraper_status = 0 if actual_num_ads == 0 else 2
            
            companies_table.update_item(
                Key={'companyId': company_id},
                UpdateExpression="SET scraperStatus = :status, dateScraped = :ds, numAds = :ads",
                ConditionExpression="scraperStatus = :expectedStatus",
                ExpressionAttributeValues={
                    ':status': final_scraper_status,
                    ':ds': now_iso,
                    ':ads': actual_num_ads,
                    ':expectedStatus': 1
                }
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                    logger.error(f"Failed to update company {company_id}: scraperStatus changed unexpectedly")
                    raise Exception("Company update failed due to concurrent modification")
            logger.error(f"Error updating company entry: {str(e)}")
            raise

        # --- Update All Jobs Tied to This Company to scraperStatus = 2 ---
        response = jobs_table.query(
            IndexName="companyId-index",
            KeyConditionExpression=Key('companyId').eq(company_id),
            FilterExpression=Attr('scraperStatus').eq(1)  # Only waiting jobs
        )
        for job in response.get('Items', []):
            jobs_table.update_item(
                Key={'jobId': job['jobId']},
                UpdateExpression="SET scraperStatus = :status, scraperRetryCount = :rc",
                ExpressionAttributeValues={':status': 2, ':rc': 0}
            )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "scraperStatus": 2,
                "triggeredScrape": True,
                "scraperRetryCount": 0,
                "numAds": actual_num_ads,
                "message": "Scraping completed successfully"
            }, default=decimal_default)
        }

    except Exception as e:
        logger.exception("Unhandled exception in scrapeHandler")
        print(f"Error: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error"})}
