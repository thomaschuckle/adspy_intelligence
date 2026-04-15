# tests/test_scrapeHandler.py
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lambdas.scrapeHandler import lambda_handler

# -----------------------------
# Fixtures
# -----------------------------
@pytest.fixture
def valid_event():
    return {
        "pathParameters": {
            "jobId": "test-job-123"
        }
    }

@pytest.fixture
def invalid_event_missing_jobid():
    return {"pathParameters": {}}

@pytest.fixture
def job_item_factory():
    def _factory(
        scraperStatus=0,
        retryCount=0,
        companyId="comp-123",
        scraperStartedAt=None,
        companyName="TestCompany",
        jobId="test-job-123"       # <-- ADD THIS
    ):
        if scraperStartedAt is None:
            scraperStartedAt = datetime.now(timezone.utc).isoformat()
        return {
            "jobId": jobId,           # <-- use the parameter
            "scraperStatus": scraperStatus,
            "scraperRetryCount": retryCount,
            "companyId": companyId,
            "scraperStartedAt": scraperStartedAt,
            "companyName": companyName
        }
    return _factory

@pytest.fixture
def company_item_factory():
    def _factory(scraperStatus=0, numAds=0, dateScraped=None, scraperStartedAt=None):
        if dateScraped is None:
            dateScraped = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        if scraperStartedAt is None:
            scraperStartedAt = datetime.now(timezone.utc).isoformat()
        return {
            "companyId": "comp-123",
            "scraperStatus": scraperStatus,
            "numAds": numAds,
            "dateScraped": dateScraped,
            "scraperStartedAt": scraperStartedAt
        }
    return _factory

# -----------------------------
# 1. Input validation -> 400
# -----------------------------
def test_missing_job_id(invalid_event_missing_jobid):
    response = lambda_handler(invalid_event_missing_jobid, None)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body

# -----------------------------
# 2. Job permanently failed -> 200
# -----------------------------
@patch("lambdas.scrapeHandler.jobs_table")
def test_job_permanently_failed(mock_jobs_table, job_item_factory):
    job_item = job_item_factory(scraperStatus=-1, retryCount=3)
    mock_jobs_table.get_item.return_value = {"Item": job_item}

    response = lambda_handler({"pathParameters": {"jobId": "test-job-123"}}, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert body["scraperStatus"] == -1
    assert body["triggeredScrape"] is False
    assert body["scraperRetryCount"] == 3

# -----------------------------
# 3. Job already completed -> 200
# -----------------------------
@patch("lambdas.scrapeHandler.jobs_table")
def test_job_already_completed(mock_jobs_table, job_item_factory):
    job_item = job_item_factory(scraperStatus=2)
    mock_jobs_table.get_item.return_value = {"Item": job_item}

    response = lambda_handler({"pathParameters": {"jobId": "test-job-123"}}, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert body["scraperStatus"] == 2
    assert body["triggeredScrape"] is False

# -----------------------------
# 4. Job waiting for another job -> 200
# -----------------------------
@patch("lambdas.scrapeHandler.jobs_table")
@patch("lambdas.scrapeHandler.companies_table")
def test_job_waiting_for_other_job(mock_companies_table, mock_jobs_table, job_item_factory, company_item_factory):
    job_item = job_item_factory(scraperStatus=0)
    company_item = company_item_factory(scraperStatus=1, numAds=0)
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}
    mock_jobs_table.update_item = MagicMock()

    response = lambda_handler({"pathParameters": {"jobId": "test-job-123"}}, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert body["scraperStatus"] == 1
    assert body["triggeredScrape"] is False
    mock_jobs_table.update_item.assert_called_once()

# -----------------------------
# 5. Lock acquisition fails -> 200
# -----------------------------
@patch("lambdas.scrapeHandler.lock_job_and_company", return_value=False)
@patch("lambdas.scrapeHandler.jobs_table")
@patch("lambdas.scrapeHandler.companies_table")
def test_lock_acquisition_fails(mock_companies_table, mock_jobs_table, mock_lock, job_item_factory, company_item_factory):
    job_item = job_item_factory(scraperStatus=0)
    company_item = company_item_factory(scraperStatus=0)
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}
    mock_jobs_table.update_item = MagicMock()

    response = lambda_handler({"pathParameters": {"jobId": "test-job-123"}}, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert body["scraperStatus"] == 1
    assert body["triggeredScrape"] is False
    mock_jobs_table.update_item.assert_called_once()

# -----------------------------
# 6. Scraping success -> 200
# -----------------------------
@patch("lambdas.scrapeHandler.scrape", return_value=(2, 5))
@patch("lambdas.scrapeHandler.lock_job_and_company", return_value=True)
@patch("lambdas.scrapeHandler.jobs_table")
@patch("lambdas.scrapeHandler.companies_table")
def test_scraping_success(mock_companies_table, mock_jobs_table, mock_lock, mock_scrape, job_item_factory, company_item_factory):
    job_item = job_item_factory(scraperStatus=0)
    company_item = company_item_factory(scraperStatus=0)
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}
    mock_jobs_table.update_item = MagicMock()
    mock_companies_table.update_item = MagicMock()
    mock_jobs_table.query = MagicMock(return_value={"Items": []})

    response = lambda_handler({"pathParameters": {"jobId": "test-job-123"}}, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert body["scraperStatus"] == 2
    assert body["triggeredScrape"] is True
    assert body["numAds"] == 5

# -----------------------------
# 7. Permanent scraper error -> 200
# -----------------------------
@patch("lambdas.scrapeHandler.scrape", side_effect=ValueError("Permanent error"))
@patch("lambdas.scrapeHandler.lock_job_and_company", return_value=True)
@patch("lambdas.scrapeHandler.jobs_table")
@patch("lambdas.scrapeHandler.companies_table")
def test_permanent_scrape_error(mock_companies_table, mock_jobs_table, mock_lock, mock_scrape, job_item_factory, company_item_factory):
    job_item = job_item_factory(scraperStatus=0, retryCount=0)
    company_item = company_item_factory()
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}
    mock_jobs_table.update_item = MagicMock()
    mock_companies_table.update_item = MagicMock()

    response = lambda_handler({"pathParameters": {"jobId": "test-job-123"}}, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert body["scraperStatus"] == -1
    assert body["triggeredScrape"] is False
    assert body["permanent"] is True
    assert "Permanent error" in body["error"]

# -----------------------------
# 8. Transient scraper error -> retry -> 200
# -----------------------------
@patch("lambdas.scrapeHandler.scrape", side_effect=Exception("Transient error"))
@patch("lambdas.scrapeHandler.lock_job_and_company", return_value=True)
@patch("lambdas.scrapeHandler.jobs_table")
@patch("lambdas.scrapeHandler.companies_table")
def test_transient_scrape_retry(mock_companies_table, mock_jobs_table, mock_lock, mock_scrape, job_item_factory, company_item_factory):
    job_item = job_item_factory(scraperStatus=0, retryCount=0)
    company_item = company_item_factory()
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}
    mock_jobs_table.update_item = MagicMock()
    mock_companies_table.update_item = MagicMock()

    response = lambda_handler({"pathParameters": {"jobId": "test-job-123"}}, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert body["scraperStatus"] == 0
    assert body["triggeredScrape"] is False
    assert body["retrying"] is True
    assert body["scraperRetryCount"] == 1

# -----------------------------
# 9. Unhandled exception -> 500
# -----------------------------
@patch("lambdas.scrapeHandler.jobs_table.get_item", side_effect=Exception("Unexpected"))
def test_unhandled_exception(mock_get_item, valid_event):
    response = lambda_handler({"pathParameters": {"jobId": "test-job-123"}}, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 500
    assert "error" in body

# -----------------------------
# 10. Concurrent jobs for same company -> single scrape trigger
# -----------------------------
@patch("lambdas.scrapeHandler.lock_job_and_company", side_effect=[True, False])
@patch("lambdas.scrapeHandler.scrape", return_value=(2, 3))
@patch("lambdas.scrapeHandler.jobs_table")
@patch("lambdas.scrapeHandler.companies_table")
def test_concurrent_jobs_single_trigger(mock_companies_table, mock_jobs_table, mock_scrape, mock_lock, job_item_factory, company_item_factory):
    # Two jobs with same company, different IDs
    job_item1 = job_item_factory(scraperStatus=0, jobId="job-1")
    job_item2 = job_item_factory(scraperStatus=0, jobId="job-2")
    company_item = company_item_factory(scraperStatus=0)
    
    # Simulate getting job1 first
    mock_jobs_table.get_item.side_effect = [
        {"Item": job_item1},
        {"Item": job_item2}
    ]
    mock_companies_table.get_item.return_value = {"Item": company_item}
    mock_jobs_table.update_item = MagicMock()
    
    # Call Lambda for both jobs
    response1 = lambda_handler({"pathParameters": {"jobId": "job-1"}}, None)
    response2 = lambda_handler({"pathParameters": {"jobId": "job-2"}}, None)
    
    body1 = json.loads(response1["body"])
    body2 = json.loads(response2["body"])
    
    # Only first job triggers scraping
    assert body1["triggeredScrape"] is True
    assert body2["triggeredScrape"] is False

# -----------------------------
# 11. Job is stale -> triggers scrape
# -----------------------------
@patch("lambdas.scrapeHandler.lock_job_and_company", return_value=True)
@patch("lambdas.scrapeHandler.scrape", return_value=(2, 4))
@patch("lambdas.scrapeHandler.jobs_table")
@patch("lambdas.scrapeHandler.companies_table")
def test_stale_job_triggers_scrape(mock_companies_table, mock_jobs_table, mock_scrape, mock_lock, job_item_factory, company_item_factory):
    stale_time = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    job_item = job_item_factory(scraperStatus=1, scraperStartedAt=stale_time)
    company_item = company_item_factory(scraperStatus=0)
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}
    mock_jobs_table.update_item = MagicMock()
    mock_companies_table.update_item = MagicMock()

    response = lambda_handler({"pathParameters": {"jobId": "test-job-123"}}, None)
    body = json.loads(response["body"])
    assert body["triggeredScrape"] is True
    assert body["scraperStatus"] == 2

# -----------------------------
# 12. Retry limit reached -> no further retries
# -----------------------------
@patch("lambdas.scrapeHandler.scrape", side_effect=Exception("Transient error"))
@patch("lambdas.scrapeHandler.lock_job_and_company", return_value=True)
@patch("lambdas.scrapeHandler.jobs_table")
@patch("lambdas.scrapeHandler.companies_table")
def test_retry_limit_reached(mock_companies_table, mock_jobs_table, mock_lock, mock_scrape, job_item_factory, company_item_factory):
    # Assume max retries = 5
    job_item = job_item_factory(scraperStatus=0, retryCount=5)
    company_item = company_item_factory(scraperStatus=0)
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}
    mock_jobs_table.update_item = MagicMock()
    mock_companies_table.update_item = MagicMock()

    response = lambda_handler({"pathParameters": {"jobId": "test-job-123"}}, None)
    body = json.loads(response["body"])

    assert body["triggeredScrape"] is False
    assert body["scraperStatus"] == -1         # Permanent failure
    assert body["permanent"] is True
    assert body["scraperRetryCount"] == 5
    assert "Transient error" in body["error"]

# -----------------------------
# 13. Scrape returns unusual values (0 ads) -> 200
# -----------------------------
@patch("lambdas.scrapeHandler.scrape", return_value=(2, 0))
@patch("lambdas.scrapeHandler.lock_job_and_company", return_value=True)
@patch("lambdas.scrapeHandler.jobs_table")
@patch("lambdas.scrapeHandler.companies_table")
def test_scrape_zero_ads(mock_companies_table, mock_jobs_table, mock_lock, mock_scrape, job_item_factory, company_item_factory):
    job_item = job_item_factory(scraperStatus=0)
    company_item = company_item_factory(scraperStatus=0)
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}
    mock_jobs_table.update_item = MagicMock()
    mock_companies_table.update_item = MagicMock()

    response = lambda_handler({"pathParameters": {"jobId": "test-job-123"}}, None)
    body = json.loads(response["body"])
    assert body["scraperStatus"] == 2
    assert body["numAds"] == 0
    assert body["triggeredScrape"] is True
