# tests/test_submitJobHandler.py
import json
import pytest
import hashlib
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root (adspy) to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lambdas.submitJobHandler import lambda_handler

# -----------------------------
# Fixtures
# -----------------------------
@pytest.fixture
def valid_event():
    """Standard valid event for testing"""
    return {
        "body": json.dumps({
            "companyName": "TestCompany",
            "sessionUuid": "123-uuid"
        })
    }

@pytest.fixture
def invalid_event():
    """Event missing required fields"""
    return {
        "body": json.dumps({})
    }

# -----------------------------
# Helpers
# -----------------------------
def generate_job_id(company_name, session_uuid):
    normalized = company_name.strip().lower()
    return hashlib.sha256(f"{normalized}-{session_uuid}".encode()).hexdigest()

# -----------------------------
# 1. Test missing parameters -> 400
# -----------------------------
def test_missing_parameters(invalid_event):
    response = lambda_handler(invalid_event, None)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body
    assert "companyName and sessionUuid" in body["error"]

# -----------------------------
# 2. Test new job creation -> 200 + jobId
# -----------------------------
@patch("lambdas.submitJobHandler.table")
def test_new_job_created(mock_table, valid_event):
    mock_table.get_item.return_value = {}
    mock_table.put_item = MagicMock()

    response = lambda_handler(valid_event, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert "jobId" in body
    assert body["message"] == "New job created"
    mock_table.put_item.assert_called_once()

# -----------------------------
# 3. Test job already exists -> 200 + existing jobId
# -----------------------------
@patch("lambdas.submitJobHandler.table")
def test_job_already_exists(mock_table, valid_event):
    job_id = generate_job_id("TestCompany", "123-uuid")
    mock_table.get_item.return_value = {"Item": {"jobId": job_id}}
    mock_table.put_item = MagicMock()

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["jobId"] == job_id
    assert body["message"] == "Job already exists"
    assert mock_table.put_item.call_count == 0

# -----------------------------
# 4. Test exception handling -> 500
# -----------------------------
@patch("lambdas.submitJobHandler.table")
def test_exception_handling(mock_table, valid_event):
    mock_table.get_item.side_effect = Exception("DynamoDB error")

    response = lambda_handler(valid_event, None)
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "error" in body
    assert "DynamoDB error" in body["error"]

# -----------------------------
# 5. Malformed JSON -> 500 (already fixed)
# -----------------------------
def test_malformed_json():
    event = {"body": "{invalid-json"}
    response = lambda_handler(event, None)
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "error" in body

# -----------------------------
# 6. Missing only companyName -> 400
# -----------------------------
def test_missing_company_name():
    event = {"body": json.dumps({"sessionUuid": "123-uuid"})}
    response = lambda_handler(event, None)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "companyName" in body["error"]

# -----------------------------
# 7. Missing only sessionUuid -> 400
# -----------------------------
def test_missing_session_uuid():
    event = {"body": json.dumps({"companyName": "TestCompany"})}
    response = lambda_handler(event, None)
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "sessionUuid" in body["error"]

# -----------------------------
# 8. Whitespace and case variation -> 200 (Lambda accepts them)
# -----------------------------
@patch("lambdas.submitJobHandler.table")
def test_whitespace_and_case_variation(mock_table):
    mock_table.get_item.return_value = {}
    mock_table.put_item = MagicMock()

    event = {
        "body": json.dumps({
            "companyName": "  TestCompany  ",
            "sessionUuid": "123-uuid"
        })
    }
    response = lambda_handler(event, None)

    # Lambda normalizes and accepts whitespace/case → returns 200
    assert response["statusCode"] == 200

# -----------------------------
# 9. Very long company name -> 400 (Lambda should reject)
# -----------------------------
@patch("lambdas.submitJobHandler.table")
def test_very_long_company_name(mock_table):
    mock_table.get_item.return_value = {}
    mock_table.put_item = MagicMock()

    long_name = "A" * 1024
    event = {"body": json.dumps({"companyName": long_name, "sessionUuid": "123-uuid"})}

    response = lambda_handler(event, None)

    # Lambda should reject company names that are too long
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "companyName" in body["error"]

# -----------------------------
# 12. DynamoDB put_item raises exception -> 500
# -----------------------------
@patch("lambdas.submitJobHandler.table")
def test_put_item_exception(mock_table, valid_event):
    mock_table.get_item.return_value = {}
    mock_table.put_item.side_effect = Exception("DynamoDB write failed")

    response = lambda_handler(valid_event, None)

    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "DynamoDB write failed" in body["error"]

# -----------------------------
# 13. Multiple job submissions -> 200
# -----------------------------
@patch("lambdas.submitJobHandler.table")
def test_multiple_jobs(mock_table):
    mock_table.get_item.return_value = {}
    mock_table.put_item = MagicMock()

    for i in range(10):
        event = {
            "body": json.dumps({
                "companyName": f"Company{i}",
                "sessionUuid": f"uuid-{i}"
            })
        }
        response = lambda_handler(event, None)
        assert response["statusCode"] == 200
