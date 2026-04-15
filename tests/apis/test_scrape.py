# tests/test_scrape.py
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import patch, MagicMock
from lambdas.scrape import lambda_handler


# -----------------------------
# Fixtures
# -----------------------------
@pytest.fixture
def valid_event():
    return {"companyId": "company-123", "jobId": "job-456"}

@pytest.fixture
def missing_params_event():
    return {"companyId": "company-123"}  # missing jobId

@pytest.fixture
def company_item():
    return {
        "companyId": "company-123",
        "companyName": "TestCompany",
        "meta_query": "meta query",
        "google_query": "google query",
        "reddit_query": "reddit query",
        "linkedin_query": "linkedin query"
    }

@pytest.fixture
def scrape_success_result():
    return (2, 5, {"meta": {"processed_images": ["img1.jpg"]}}, None)

@pytest.fixture
def scrape_permanent_error_result():
    return (0, 0, {}, {"type": "permanent", "message": "Permanent scrape failure"})

@pytest.fixture
def scrape_transient_error_result():
    return (0, 0, {}, {"type": "transient", "message": "Transient scrape failure"})


# -----------------------------
# 1. Missing parameters -> raises ValueError
# -----------------------------
def test_missing_parameters(missing_params_event):
    with pytest.raises(ValueError) as excinfo:
        lambda_handler(missing_params_event, None)
    assert "Missing required parameters" in str(excinfo.value)


# -----------------------------
# 2. Company not found -> raises ValueError
# -----------------------------
@patch("lambdas.scrape.companies_table")
def test_company_not_found(mock_companies_table, valid_event):
    mock_companies_table.get_item.return_value = {"Item": None}
    with pytest.raises(ValueError) as excinfo:
        lambda_handler(valid_event, None)
    assert "Company not found" in str(excinfo.value)


# -----------------------------
# 3. Successful scrape -> returns status=2
# -----------------------------
@patch("lambdas.scrape.companies_table")
@patch("lambdas.scrape.scrape")
@patch("lambdas.scrape.trigger_n8n_workflow")
def test_scrape_success(mock_trigger, mock_scrape, mock_companies_table, valid_event, company_item, scrape_success_result):
    mock_companies_table.get_item.return_value = {"Item": company_item}
    mock_scrape.return_value = scrape_success_result

    response = lambda_handler(valid_event, None)
    assert response["status"] == 2
    assert response["numAds"] == 5
    mock_trigger.assert_called_once()


# -----------------------------
# 4. Permanent scrape error -> raises ValueError
# -----------------------------
@patch("lambdas.scrape.companies_table")
@patch("lambdas.scrape.scrape")
def test_scrape_permanent_error(mock_scrape, mock_companies_table, valid_event, company_item, scrape_permanent_error_result):
    mock_companies_table.get_item.return_value = {"Item": company_item}
    mock_scrape.return_value = scrape_permanent_error_result

    with pytest.raises(ValueError) as excinfo:
        lambda_handler(valid_event, None)
    assert "Permanent scrape failure" in str(excinfo.value)


# -----------------------------
# 5. Transient scrape error -> raises Exception
# -----------------------------
@patch("lambdas.scrape.companies_table")
@patch("lambdas.scrape.scrape")
def test_scrape_transient_error(mock_scrape, mock_companies_table, valid_event, company_item, scrape_transient_error_result):
    mock_companies_table.get_item.return_value = {"Item": company_item}
    mock_scrape.return_value = scrape_transient_error_result

    with pytest.raises(Exception) as excinfo:
        lambda_handler(valid_event, None)
    assert "Transient scrape failure" in str(excinfo.value)


# -----------------------------
# 6. DynamoDB fetch error -> raises Exception
# -----------------------------
@patch("lambdas.scrape.companies_table")
def test_dynamodb_fetch_error(mock_companies_table, valid_event):
    mock_companies_table.get_item.side_effect = Exception("DynamoDB error")
    with pytest.raises(Exception) as excinfo:
        lambda_handler(valid_event, None)
    assert "DynamoDB error" in str(excinfo.value)


# -----------------------------
# 7. Missing companyName -> raises ValueError
# -----------------------------
@patch("lambdas.scrape.companies_table")
def test_missing_company_name(mock_companies_table, valid_event):
    mock_companies_table.get_item.return_value = {"Item": {"companyId": "company-123"}}
    with pytest.raises(ValueError) as excinfo:
        lambda_handler(valid_event, None)
    assert "Invalid or missing company name" in str(excinfo.value)

# -----------------------------
# 8. Successful scrape but no processed images -> workflow not triggered
# -----------------------------
@patch("lambdas.scrape.companies_table")
@patch("lambdas.scrape.scrape")
@patch("lambdas.scrape.trigger_n8n_workflow")
def test_scrape_no_processed_images(mock_trigger, mock_scrape, mock_companies_table, valid_event, company_item):
    mock_companies_table.get_item.return_value = {"Item": company_item}
    # Scrape returns results with empty processed_images
    mock_scrape.return_value = (2, 5, {"meta": {"processed_images": []}}, None)

    response = lambda_handler(valid_event, None)
    assert response["status"] == 2
    assert response["numAds"] == 5
    # Workflow should not be triggered
    mock_trigger.assert_not_called()


# -----------------------------
# 9. Partial DB query fields -> prepare_queries() called
# -----------------------------
@patch("lambdas.scrape.companies_table")
@patch("lambdas.scrape.prepare_queries")
@patch("lambdas.scrape.scrape")
@patch("lambdas.scrape.trigger_n8n_workflow")
def test_partial_db_queries(mock_trigger, mock_scrape, mock_prepare, mock_companies_table, valid_event):
    company_item_partial = {
        "companyId": "company-123",
        "companyName": "TestCompany",
        "meta_query": None,
        "google_query": "google query",
        "reddit_query": None,
        "linkedin_query": None
    }
    mock_companies_table.get_item.return_value = {"Item": company_item_partial}
    mock_prepare.return_value = {
        "meta_query": "generated_meta",
        "reddit_query": "generated_reddit",
        "linkedin_query": "generated_linkedin"
    }
    mock_scrape.return_value = (2, 3, {"meta": {"processed_images": ["img1.jpg"]}}, None)

    response = lambda_handler(valid_event, None)
    assert response["status"] == 2
    assert response["numAds"] == 3
    # Should call prepare_queries for missing queries
    mock_prepare.assert_called_once()
    mock_trigger.assert_called_once()


# -----------------------------
# 10. No platforms scraped, zero ads -> API still succeeds
# -----------------------------
@patch("lambdas.scrape.companies_table")
@patch("lambdas.scrape.scrape")
@patch("lambdas.scrape.trigger_n8n_workflow")
def test_no_platforms_scraped(mock_trigger, mock_scrape, mock_companies_table, valid_event, company_item):
    mock_companies_table.get_item.return_value = {"Item": company_item}
    # Zero platforms scraped, zero ads
    mock_scrape.return_value = (0, 0, {}, None)

    response = lambda_handler(valid_event, None)
    assert response["status"] == 2
    assert response["numAds"] == 0
    mock_trigger.assert_not_called()


# -----------------------------
# 11. Unexpected empty results dict -> API does not fail
# -----------------------------
@patch("lambdas.scrape.companies_table")
@patch("lambdas.scrape.scrape")
@patch("lambdas.scrape.trigger_n8n_workflow")
def test_empty_results_dict(mock_trigger, mock_scrape, mock_companies_table, valid_event, company_item):
    mock_companies_table.get_item.return_value = {"Item": company_item}
    # Scrape returns empty dict for results
    mock_scrape.return_value = (2, 2, {}, None)

    response = lambda_handler(valid_event, None)
    assert response["status"] == 2
    assert response["numAds"] == 2
    mock_trigger.assert_not_called()


# -----------------------------
# 12. Transient scrape error with string message -> raises Exception
# -----------------------------
@patch("lambdas.scrape.companies_table")
@patch("lambdas.scrape.scrape")
def test_transient_error_string_message(mock_scrape, mock_companies_table, valid_event, company_item):
    mock_companies_table.get_item.return_value = {"Item": company_item}
    # Scrape returns transient error as string instead of dict
    mock_scrape.return_value = (0, 0, {}, Exception("Transient error during scraping"))

    with pytest.raises(Exception) as excinfo:
        lambda_handler(valid_event, None)
    assert "Transient error during scraping" in str(excinfo.value)
