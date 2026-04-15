# tests/test_fetchImages.py
import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from lambdas.fetchImages import lambda_handler, safe_name

# -----------------------------
# Fixtures
# -----------------------------
@pytest.fixture
def valid_event():
    return {
        "pathParameters": {
            "jobId": "job-123"
        }
    }

@pytest.fixture
def job_item():
    return {
        "jobId": "job-123",
        "companyId": "comp-456"
    }

@pytest.fixture
def company_item():
    return {
        "companyId": "comp-456",
        "companyName": "Test Company"
    }

@pytest.fixture
def s3_objects():
    return [
        {"Key": "raw/images/test_company/img1.jpg"},
        {"Key": "raw/images/test_company/img2.png"},
        {"Key": "raw/images/test_company/readme.txt"}  # non-image
    ]

@pytest.fixture
def s3_objects_uppercase():
    return [
        {"Key": "raw/images/test_company/IMG1.JPG"},
        {"Key": "raw/images/test_company/IMG2.PNG"},
        {"Key": "raw/images/test_company/readme.TXT"}
    ]

# -----------------------------
# 1. Missing or invalid jobId → 400
# -----------------------------
@pytest.mark.parametrize("event", [
    {"pathParameters": {}},
    {"pathParameters": {"jobId": ""}},
    {"pathParameters": {"jobId": None}},
    {"pathParameters": None},
    None
])
def test_missing_or_invalid_job_id(event):
    response = lambda_handler(event, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 400
    assert body["numImages"] == 0
    assert body["images"] == []

# -----------------------------
# 2. Job not found → 404
# -----------------------------
@patch("lambdas.fetchImages.JOBS_TABLE")
def test_job_not_found(mock_jobs_table, valid_event):
    mock_jobs_table.get_item.return_value = {}
    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 404
    assert "Job job-123 not found" in body["error"]
    assert body["numImages"] == 0

# -----------------------------
# 3. Company not found → 404
# -----------------------------
@patch("lambdas.fetchImages.JOBS_TABLE")
@patch("lambdas.fetchImages.COMPANIES_TABLE")
def test_company_not_found(mock_companies_table, mock_jobs_table, valid_event, job_item):
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {}
    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 404
    assert "Company comp-456 not found" in body["error"]
    assert body["numImages"] == 0

# -----------------------------
# 4. No images found → 200
# -----------------------------
@patch("lambdas.fetchImages.s3")
@patch("lambdas.fetchImages.JOBS_TABLE")
@patch("lambdas.fetchImages.COMPANIES_TABLE")
def test_no_images(mock_companies_table, mock_jobs_table, mock_s3, valid_event, job_item, company_item):
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}
    
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [{"Contents": []}]
    mock_s3.get_paginator.return_value = mock_paginator

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert body["numImages"] == 0
    assert body["images"] == []

# -----------------------------
# 5. Images found → 200
# -----------------------------
@patch("lambdas.fetchImages.s3")
@patch("lambdas.fetchImages.JOBS_TABLE")
@patch("lambdas.fetchImages.COMPANIES_TABLE")
def test_images_found(mock_companies_table, mock_jobs_table, mock_s3, valid_event, job_item, company_item, s3_objects):
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}
    
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [{"Contents": s3_objects}]
    mock_s3.get_paginator.return_value = mock_paginator
    
    mock_s3.generate_presigned_url.side_effect = lambda *args, **kwargs: f"https://fake-s3/{kwargs['Params']['Key']}"

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert body["numImages"] == 2
    assert len(body["images"]) == 2
    assert all(img["url"].startswith("https://fake-s3/") for img in body["images"])
    assert all(img["key"].endswith((".jpg", ".png")) for img in body["images"])

# -----------------------------
# 6. Uppercase image extensions → 200
# -----------------------------
@patch("lambdas.fetchImages.s3")
@patch("lambdas.fetchImages.JOBS_TABLE")
@patch("lambdas.fetchImages.COMPANIES_TABLE")
def test_images_uppercase_extensions(mock_companies_table, mock_jobs_table, mock_s3, valid_event, job_item, company_item, s3_objects_uppercase):
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}
    
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [{"Contents": s3_objects_uppercase}]
    mock_s3.get_paginator.return_value = mock_paginator
    
    mock_s3.generate_presigned_url.side_effect = lambda *args, **kwargs: f"https://fake-s3/{kwargs['Params']['Key']}"

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert body["numImages"] == 2
    assert all(img["key"].lower().endswith((".jpg", ".png")) for img in body["images"])

# -----------------------------
# 7. Multiple S3 pages → 200
# -----------------------------
@patch("lambdas.fetchImages.s3")
@patch("lambdas.fetchImages.JOBS_TABLE")
@patch("lambdas.fetchImages.COMPANIES_TABLE")
def test_multiple_s3_pages(mock_companies_table, mock_jobs_table, mock_s3, valid_event, job_item, company_item):
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}

    page1 = {"Contents": [{"Key": "raw/images/test_company/img1.jpg"}]}
    page2 = {"Contents": [{"Key": "raw/images/test_company/img2.png"}]}
    mock_s3.get_paginator.return_value.paginate.return_value = [page1, page2]

    mock_s3.generate_presigned_url.side_effect = lambda *args, **kwargs: f"https://fake-s3/{kwargs['Params']['Key']}"
    
    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])
    assert body["numImages"] == 2
    keys = [img["key"].split("/")[-1] for img in body["images"]]
    assert "img1.jpg" in keys and "img2.png" in keys


# -----------------------------
# 8. Company name with special characters → 200
# -----------------------------
@patch("lambdas.fetchImages.s3")
@patch("lambdas.fetchImages.JOBS_TABLE")
@patch("lambdas.fetchImages.COMPANIES_TABLE")
def test_company_special_chars(mock_companies_table, mock_jobs_table, mock_s3, valid_event, job_item):
    special_company = {"companyId": "comp-456", "companyName": "Test!@# Company"}
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": special_company}

    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [{"Contents": [{"Key": "raw/images/test___company/img1.jpg"}]}]
    mock_s3.get_paginator.return_value = mock_paginator

    mock_s3.generate_presigned_url.side_effect = lambda *args, **kwargs: f"https://fake-s3/{kwargs['Params']['Key']}"
    
    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])
    assert body["numImages"] == 1
    assert "test___company" in body["images"][0]["key"]

# -----------------------------
# 9. S3 generate_presigned_url failure → 500
# -----------------------------
@patch("lambdas.fetchImages.s3")
@patch("lambdas.fetchImages.JOBS_TABLE")
@patch("lambdas.fetchImages.COMPANIES_TABLE")
def test_s3_presigned_failure(mock_companies_table, mock_jobs_table, mock_s3, valid_event, job_item, company_item):
    mock_jobs_table.get_item.return_value = {"Item": job_item}
    mock_companies_table.get_item.return_value = {"Item": company_item}
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [{"Contents": [{"Key": "raw/images/test_company/img1.jpg"}]}]
    mock_s3.get_paginator.return_value = mock_paginator

    mock_s3.generate_presigned_url.side_effect = Exception("S3 down")

    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 500
    assert "S3 down" in body["error"]

# -----------------------------
# 10. Internal DynamoDB error → 500
# -----------------------------
@patch("lambdas.fetchImages.JOBS_TABLE.get_item", side_effect=Exception("DynamoDB down"))
def test_internal_error(mock_jobs_get, valid_event):
    response = lambda_handler(valid_event, None)
    body = json.loads(response["body"])
    assert response["statusCode"] == 500
    assert "DynamoDB down" in body["error"]
