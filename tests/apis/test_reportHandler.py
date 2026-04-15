# tests/test_reportHandler.py
import sys
import os
import pytest
import json
from unittest.mock import patch, MagicMock
from lambdas.reportHandler import lambda_handler

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# -----------------------------
# Fixtures
# -----------------------------
@pytest.fixture
def valid_event():
    return {"pathParameters": {"jobId": "job-123"}}


@pytest.fixture
def job_item_base():
    return {
        "jobId": "job-123",
        "companyId": "comp-456",
        "reportStatus": 0,
        "scraperStatus": 2,
        "image2textStatus": 2,
        "reportRetryCount": 0,
        "dataCheckRetryCount": 0
    }


@pytest.fixture
def company_item():
    return {
        "companyId": "comp-456",
        "companyName": "Test Company",
        "numAds": 5
    }


# -----------------------------
# 1. Report already exists -> returns status 2 with existing reportPath
# -----------------------------
@patch("lambdas.reportHandler.jobs_table")
@patch("lambdas.reportHandler.companies_table")
@patch("lambdas.reportHandler.s3")
@patch("lambdas.reportHandler.trigger_report_workflow")
def test_report_already_exists(mock_workflow, mock_s3, mock_companies_table, mock_jobs_table,
                               valid_event, job_item_base, company_item):
    job_item = job_item_base.copy()
    job_item["reportPath"] = "reports/job-123/report.json"
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["reportStatus"] == 2
    assert body["reportPath"] == job_item["reportPath"]
    assert "already generated" in body["message"]


# -----------------------------
# 2. Scraper not complete -> report cannot start, returns status 0
# -----------------------------
@patch("lambdas.reportHandler.jobs_table")
@patch("lambdas.reportHandler.companies_table")
def test_scraper_not_complete(mock_companies_table, mock_jobs_table, valid_event, job_item_base, company_item):
    job_item = job_item_base.copy()
    job_item["scraperStatus"] = 1
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["reportStatus"] == 0
    assert body["scraperStatus"] == 1
    assert "scraping not complete" in body["message"]


# -----------------------------
# 3. Image2Text in progress -> report cannot start, returns status 1
# -----------------------------
@patch("lambdas.reportHandler.jobs_table")
@patch("lambdas.reportHandler.companies_table")
def test_image2text_in_progress(mock_companies_table, mock_jobs_table, valid_event, job_item_base, company_item):
    job_item = job_item_base.copy()
    job_item["image2textStatus"] = 1
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["reportStatus"] == 1
    assert body["image2textStatus"] == 1
    assert "Waiting for image extraction" in body["message"]


# -----------------------------
# 4. Empty report after max retries -> generates empty report, status 2
# -----------------------------
@patch("lambdas.reportHandler.jobs_table")
@patch("lambdas.reportHandler.companies_table")
@patch("lambdas.reportHandler.s3")
@patch("lambdas.reportHandler.check_s3_folder_has_usable_data")
def test_empty_report_generated(mock_check_s3, mock_s3, mock_companies_table, mock_jobs_table,
                                valid_event, job_item_base, company_item):
    job_item = job_item_base.copy()
    job_item["dataCheckRetryCount"] = 3
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}

    mock_check_s3.return_value = False
    mock_s3.put_object.return_value = {}

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["reportStatus"] == 2
    assert body["reportPath"].startswith("reports/job-123/")
    assert "Empty report generated" in body["message"]


# -----------------------------
# 5. Report generation starts with usable data -> triggers workflow, status 1
# -----------------------------
@patch("lambdas.reportHandler.jobs_table")
@patch("lambdas.reportHandler.companies_table")
@patch("lambdas.reportHandler.check_s3_folder_has_usable_data")
@patch("lambdas.reportHandler.trigger_report_workflow")
def test_report_generation_starts(mock_workflow, mock_check_s3, mock_companies_table, mock_jobs_table,
                                  valid_event, job_item_base, company_item):
    mock_jobs_table.get_item.return_value = {"Item": job_item_base}
    mock_companies_table.get_item.return_value = {"Item": company_item}

    mock_check_s3.return_value = True
    mock_workflow.return_value = True

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["reportStatus"] == 1
    assert "started" in body["message"]


# -----------------------------
# 6. Invalid jobId -> returns 400
# -----------------------------
def test_invalid_job_id():
    event = {"pathParameters": {"jobId": ""}}
    response = lambda_handler(event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 400
    assert "jobId is required" in body["message"]


# -----------------------------
# 7. Job not found -> returns 404
# -----------------------------
@patch("lambdas.reportHandler.jobs_table")
def test_job_not_found(mock_jobs_table, valid_event):
    mock_jobs_table.get_item.return_value = {"Item": None}
    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 404


# -----------------------------
# 8. Company not found -> returns 404
# -----------------------------
@patch("lambdas.reportHandler.jobs_table")
@patch("lambdas.reportHandler.companies_table")
def test_company_not_found(mock_companies_table, mock_jobs_table, valid_event, job_item_base):
    mock_jobs_table.get_item.return_value = {"Item": job_item_base}
    mock_companies_table.get_item.return_value = {"Item": None}

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 404


# -----------------------------
# 9. Scraper permanently failed -> report inherits failure, status -1
# -----------------------------
@patch("lambdas.reportHandler.jobs_table")
@patch("lambdas.reportHandler.companies_table")
def test_scraper_permanent_failure(mock_companies_table, mock_jobs_table, valid_event, job_item_base, company_item):
    job_item = job_item_base.copy()
    job_item["scraperStatus"] = -1
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["reportStatus"] == -1
    assert body["permanent"] is True
    assert "scraping failed permanently" in body["message"]


# -----------------------------
# 10. Workflow permanent error -> reportStatus -1, retryCount NOT incremented
# -----------------------------
@patch("lambdas.reportHandler.jobs_table")
@patch("lambdas.reportHandler.companies_table")
@patch("lambdas.reportHandler.check_s3_folder_has_usable_data")
@patch("lambdas.reportHandler.trigger_report_workflow")
def test_workflow_permanent_error(mock_workflow, mock_check_s3, mock_companies_table, mock_jobs_table,
                                  valid_event, job_item_base, company_item):
    # GIVEN: a job ready to generate report
    job_item = job_item_base.copy()
    job_item["reportRetryCount"] = 2  # existing retry count

    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}
    mock_check_s3.return_value = True

    # Simulate permanent failure in workflow
    mock_workflow.side_effect = ValueError("Permanent workflow error")

    # WHEN
    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])

    # THEN
    assert response["statusCode"] == 200
    assert body["reportStatus"] == -1
    assert body["permanent"] is True
    assert "Permanent workflow error" in body["message"]
    assert body["retryCount"] == 2  # confirm NOT incremented

    # Optional: ensure DynamoDB update sets reportStatus=-1 and leaves retry count unchanged
    mock_jobs_table.update_item.assert_called_with(
        Key={"jobId": "job-123"},
        UpdateExpression="SET reportStatus = :status, reportRetryCount = :rc",
        ExpressionAttributeValues={":status": -1, ":rc": 2}
    )
