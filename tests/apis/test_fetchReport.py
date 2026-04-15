# tests/test_fetchReport.py
import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lambdas.fetchReport import lambda_handler

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
        "companyName": "Test Company",
        "reportPath": "reports/job-123/report.json",
        "reportStatus": 2  # Report generated successfully
    }

# -----------------------------
# 1. Missing or invalid jobId → 400
# -----------------------------
@pytest.mark.parametrize("event", [
    {"pathParameters": {}},
    {"pathParameters": {"jobId": ""}},
    {"pathParameters": {"jobId": None}},
    {"pathParameters": None}
])
def test_missing_or_invalid_job_id(event):
    response = lambda_handler(event, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 400
    assert "Invalid or missing jobId" == body["error"]
    assert "jobId is required" in body["message"]

# -----------------------------
# 2. Job not found → 404
# -----------------------------
@patch("lambdas.fetchReport.jobs_table")
def test_job_not_found(mock_jobs_table, valid_event):
    mock_jobs_table.get_item.return_value = {"Item": None}
    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 404
    assert body["error"] == "Job not found"
    assert "No job exists with ID job-123" in body["message"]

# -----------------------------
# 3. Report not generated yet → 404
# -----------------------------
@patch("lambdas.fetchReport.jobs_table")
def test_report_not_generated(mock_jobs_table, valid_event, job_item_base):
    job_item = job_item_base.copy()
    job_item["reportPath"] = ""
    job_item["reportStatus"] = 0
    mock_jobs_table.get_item.return_value = {"Item": job_item}

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 404
    assert body["error"] == "Report not found"
    assert body["reportStatus"] == 0
    assert "No report has been generated" in body["message"]

# -----------------------------
# 4. Report generation in progress → 200, status 1
# -----------------------------
@patch("lambdas.fetchReport.jobs_table")
def test_report_in_progress(mock_jobs_table, valid_event, job_item_base):
    job_item = job_item_base.copy()
    job_item["reportPath"] = ""
    job_item["reportStatus"] = 1
    mock_jobs_table.get_item.return_value = {"Item": job_item}

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert body["error"] == "Report not ready"
    assert body["reportStatus"] == 1
    assert "still being generated" in body["message"]

# -----------------------------
# 5. Report generation failed → 200, status -1
# -----------------------------
@patch("lambdas.fetchReport.jobs_table")
def test_report_generation_failed(mock_jobs_table, valid_event, job_item_base):
    job_item = job_item_base.copy()
    job_item["reportPath"] = ""
    job_item["reportStatus"] = -1
    mock_jobs_table.get_item.return_value = {"Item": job_item}

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert body["error"] == "Report generation failed"
    assert body["reportStatus"] == -1
    assert "permanently failed" in body["message"]

# -----------------------------
# 6. Report exists → presigned URL generated
# -----------------------------
@patch("lambdas.fetchReport.s3")
@patch("lambdas.fetchReport.jobs_table")
def test_report_success(mock_jobs_table, mock_s3, valid_event, job_item_base):
    mock_jobs_table.get_item.return_value = {"Item": job_item_base}
    mock_s3.generate_presigned_url.return_value = "https://fake-s3/reports/job-123/report.json"

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert body["reportUrl"].startswith("https://fake-s3/")
    assert body["reportPath"] == job_item_base["reportPath"]
    assert body["companyName"] == job_item_base["companyName"]
    assert body["expiresIn"] == 3600
    assert "generated successfully" in body["message"]

# -----------------------------
# 7. S3 presigned URL failure → 500
# -----------------------------
@patch("lambdas.fetchReport.s3")
@patch("lambdas.fetchReport.jobs_table")
def test_s3_presigned_failure(mock_jobs_table, mock_s3, valid_event, job_item_base):
    mock_jobs_table.get_item.return_value = {"Item": job_item_base}
    mock_s3.generate_presigned_url.side_effect = Exception("S3 down")

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 500
    # Updated assertion to match actual Lambda message
    assert "failed to create download link" in body["message"].lower()
    assert "s3 down" in body["message"].lower()

# -----------------------------
# 8. DynamoDB exception → 500
# -----------------------------
@patch("lambdas.fetchReport.jobs_table")
def test_dynamodb_failure(mock_jobs_table, valid_event):
    mock_jobs_table.get_item.side_effect = Exception("DynamoDB down")

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 500
    assert "Failed to retrieve job" in body["message"]

