# tests/test_updateFields.py
import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock
from lambdas.updateFields import lambda_handler

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# -----------------------------
# Fixtures
# -----------------------------
@pytest.fixture
def valid_event():
    return {
        "body": json.dumps({
            "companyId": "comp-123",
            "jobId": "job-456",
            "fieldToUpdate": "image2textStatus",
            "updatedValue": 2,
            "tables": "jobs,companies"
        })
    }

@pytest.fixture
def job_item():
    return {"jobId": "job-456", "image2textStatus": 1}

@pytest.fixture
def company_item():
    return {"companyId": "comp-123", "image2textStatus": 1}


# -----------------------------
# 1. Success -> All tables updated
# -----------------------------
@patch("lambdas.updateFields.dynamodb")
def test_update_all_success(mock_dynamodb, valid_event, job_item, company_item):
    # Mock tables
    mock_jobs_table = MagicMock()
    mock_companies_table = MagicMock()
    mock_dynamodb.Table.side_effect = [mock_jobs_table, mock_companies_table]

    # Mock get_item to return existing items
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}

    # Mock update_item to return updated attributes
    mock_jobs_table.update_item.return_value = {"Attributes": {"image2textStatus": 2}}
    mock_companies_table.update_item.return_value = {"Attributes": {"image2textStatus": 2}}

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["success"] is True
    assert body["summary"]["succeeded"] == 2
    assert all(r["success"] for r in body["results"])


# -----------------------------
# 2. Partial success -> One table fails
# -----------------------------
@patch("lambdas.updateFields.dynamodb")
def test_partial_success(mock_dynamodb, valid_event, job_item, company_item):
    mock_jobs_table = MagicMock()
    mock_companies_table = MagicMock()
    mock_dynamodb.Table.side_effect = [mock_jobs_table, mock_companies_table]

    # Jobs exists, companies missing
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_jobs_table.update_item.return_value = {"Attributes": {"image2textStatus": 2}}
    mock_companies_table.get_item.return_value = {}  # missing
    # update_item should not be called for missing item

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 404
    assert body["success"] is False
    assert body["summary"]["succeeded"] == 1
    assert body["summary"]["failed"] == 1
    assert any(r.get("error") == "Item not found" for r in body["results"])


# -----------------------------
# 3. Invalid input -> 400
# -----------------------------
def test_invalid_input_missing_fields():
    event = {"body": json.dumps({"jobId": "job-1"})}  # missing companyId, fieldToUpdate, tables
    response = lambda_handler(event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 400
    assert body["success"] is False
    assert len(body["errors"]) >= 3  # multiple validation errors


# -----------------------------
# 4. Field not allowed -> 400
# -----------------------------
def test_field_not_allowed():
    event = {
        "body": json.dumps({
            "companyId": "comp-123",
            "jobId": "job-456",
            "fieldToUpdate": "notAllowedField",
            "updatedValue": 2,
            "tables": "jobs,companies"
        })
    }
    response = lambda_handler(event, None)
    body = json.loads(response["body"])

    assert response["statusCode"] == 400
    assert body["success"] is False
    assert any("not allowed" in e for e in body["errors"])


# -----------------------------
# 5. Internal server error -> 500
# -----------------------------
@patch("lambdas.updateFields.dynamodb")
def test_internal_error(mock_dynamodb, valid_event):
    """
    Scenario:
    - Both tables are included in the request
    - DynamoDB get_item throws an exception for all tables
    Expected:
    - Lambda returns 207 Multi-Status
    - Each table result indicates failure with the error message
    """
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    mock_table.get_item.side_effect = Exception("DynamoDB failure")

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])

    # -> Multi-table failures return 207 if not 404
    assert response["statusCode"] == 207
    assert body["success"] is False

    # -> Check that each table result has the expected error
    for result in body["results"]:
        assert result["success"] is False
        assert "DynamoDB failure" in result["error"]

    # -> Check summary counts
    assert body["summary"]["total"] == len(body["results"])
    assert body["summary"]["succeeded"] == 0
    assert body["summary"]["failed"] == len(body["results"])
