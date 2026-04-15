"""
updateFields API

Behavior Overview:
-----------------
This Lambda updates specific fields in one or more DynamoDB tables (`jobs` and `companies`).
It ensures the record exists before updating and returns detailed status per table.

API endpoint: https://<YOUR-AWS-API>/dev/jobs/fields
Method: POST

API input body:
{
    "companyId": str,          # Identifier for the company (used for `companies` table)
    "jobId": str,              # Identifier for the job (used for `jobs` table)
    "fieldToUpdate": str,      # Name of the field to update (must be whitelisted)
    "updatedValue": any,       # New value to set for the field
    "tables": str              # Comma-separated table names; e.g. "jobs,companies"

}

All API output scenarios:
------------------------
1. Success - Field Updated:
    Status Code: 200
    Body: {
        "success": True,
        "message": "All updates completed successfully",
        "results": [
            {
                "table": str,           # Name of the table updated
                "success": True,
                "data": dict           # Updated attributes from DynamoDB
            },
            ...
        ],
        "summary": {
            "total": int,
            "succeeded": int,
            "failed": int
        }
    }
2. Partial Success - Some Updates Failed:
    Status Code: 207
    Body: {
        "success": False,
        "message": "Some updates failed",
        "results": [
            {
                "table": str,
                "success": False,
                "error": str           # Error message for the failure
            },
            ...
        ],
        "summary": {
            "total": int,
            "succeeded": int,
            "failed": int
        }
    }
3. Error - Item Not Found:
    Status Code: 404
    Body: {
        "success": False,
        "message": "One or more items not found",
        "results": [
            {
                "table": str,
                "success": False,
                "error": "Item not found"
            },
            ...
        ],
        "summary": {...}
    }
4. Error - Invalid Input / Missing Parameters:
    Status Code: 400
    Body: {
        "success": False,
        "errors": [str, ...]       # List of validation errors
    }
5. Error - Internal Server Error:
    Status Code: 500
    Body: {
        "success": False,
        "message": "Internal server error",
        "results": [ ... ]         # Optional per-table results
    }

Key Points:
1. Whitelisted fields prevent unsafe updates; only `image2textStatus` is currently allowed.
2. Each table uses its natural key for lookups:
    - `jobs`: looked up by `jobId` only
    - `companies`: looked up by `companyId` only
3. The Lambda performs a **get_item** before updating to enforce existence checks and return 404 if missing.
4. Updates are performed using **update_item** with `ReturnValues='ALL_NEW'` to return the updated attributes.
5. Supports multiple tables in one request:
    - Each table is updated individually, and results are aggregated.
6. Response summary includes:
    - `total`: number of tables attempted
    - `succeeded`: number of successful updates
    - `failed`: number of failed updates
7. Designed to integrate with n8n or other automation workflows for programmatic field updates.

Fields affected in DynamoDB:
----------------------------
- `jobs` table:
    - image2textStatus  # Updated by this Lambda
    - jobId (PK)        # Used for lookup, not modified
- `companies` table:
    - image2textStatus  # Updated by this Lambda
    - companyId (PK)    # Used for lookup, not modified

"""

import json
import boto3
from datetime import datetime
from botocore.exceptions import ClientError
from decimal import Decimal

# -------------------- Setup -------------------- #

dynamodb = boto3.resource('dynamodb')

ALLOWED_TABLES = {
    'jobs': ['image2textStatus', 'reportStatus', 'reportRetryCount', 'reportPath'],
    'companies': ['image2textStatus'],
}

# -------------------- Helpers -------------------- #

def create_response(status_code: int, body: dict) -> dict:
    def decimal_default(obj):
        if isinstance(obj, Decimal):
            # Convert to int if whole number, else float
            return int(obj) if obj % 1 == 0 else float(obj)
        raise TypeError

    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(body, default=decimal_default)
    }


def validate_request(body: dict) -> list:
    errors = []

    if not body.get('companyId') or not isinstance(body['companyId'], str):
        errors.append("companyId is required and must be a string")
    if not body.get('jobId') or not isinstance(body['jobId'], str):
        errors.append("jobId is required and must be a string")
    if not body.get('fieldToUpdate') or not isinstance(body['fieldToUpdate'], str):
        errors.append("fieldToUpdate is required and must be a string")
    if 'updatedValue' not in body:
        errors.append("updatedValue is required")
    if not body.get('tables'):
        errors.append("tables is required and must be a non-empty string or list")


    field = body.get('fieldToUpdate')
    tables = body.get('tables', [])
    for table in tables:
        if table not in ALLOWED_TABLES:
            errors.append(f"Table '{table}' is not allowed")
        elif field not in ALLOWED_TABLES.get(table, []):
            errors.append(f"Field '{field}' is not allowed in table '{table}'")

    return errors

def update_table_field(table_name: str, company_id: str, job_id: str, field: str, value) -> dict:
    """Update a single field; return 404 if item not found. Key depends on table."""
    table = dynamodb.Table(table_name)

    # Determine the correct key for this table
    if table_name == 'jobs':
        key = {'jobId': job_id}
    elif table_name == 'companies':
        key = {'companyId': company_id}
    else:
        # Should not happen because of whitelist validation
        return {'table': table_name, 'success': False, 'error': 'Invalid table', 'statusCode': 400}

    try:
        # Check if item exists
        item = table.get_item(Key=key)
        if 'Item' not in item:
            return {'table': table_name, 'success': False, 'error': 'Item not found', 'statusCode': 404}

        # Update the field
        response = table.update_item(
            Key=key,
            UpdateExpression='SET #field = :value',
            ExpressionAttributeNames={'#field': field},
            ExpressionAttributeValues={':value': value},
            ReturnValues='ALL_NEW'
        )
        return {'table': table_name, 'success': True, 'data': response.get('Attributes', {})}

    except ClientError as e:
        return {'table': table_name, 'success': False, 'error': e.response['Error']['Message'], 'statusCode': 500}
    except Exception as e:
        return {'table': table_name, 'success': False, 'error': str(e), 'statusCode': 500}

# -------------------- Lambda Handler -------------------- #

# -------------------- Lambda Handler -------------------- #

def lambda_handler(event, context):
    # Parse body
    try:
        body = json.loads(event.get('body') or '{}')
    except json.JSONDecodeError as e:
        return create_response(400, {'success': False, 'error': f'Invalid JSON: {str(e)}'})

    # -------------------- Normalize and trim input -------------------- #
    for key in ['companyId', 'jobId', 'fieldToUpdate']:
        if key in body and isinstance(body[key], str):
            body[key] = body[key].strip()

    # Trim updatedValue if it’s a string
    if 'updatedValue' in body and isinstance(body['updatedValue'], str):
        body['updatedValue'] = body['updatedValue'].strip()

    # Convert tables string to list if comma-separated, and trim spaces
    if isinstance(body.get('tables'), str):
        body['tables'] = [t.strip() for t in body['tables'].split(',') if t.strip()]
    elif isinstance(body.get('tables'), list):
        body['tables'] = [t.strip() for t in body['tables'] if isinstance(t, str) and t.strip()]

    # Convert tables string to list if comma-separated
    if isinstance(body.get('tables'), str):
        body['tables'] = [t.strip() for t in body['tables'].split(',') if t.strip()]

    # Validate request
    errors = validate_request(body)
    if errors:
        return create_response(400, {'success': False, 'errors': errors})

    # Attempt to convert updatedValue to int if possible
    value = body['updatedValue']
    try:
        value = int(value)
    except (ValueError, TypeError):
        pass  # keep original value if cannot convert

    # Update all tables
    results = []
    for table in body['tables']:
        result = update_table_field(
            table_name=table,
            company_id=body['companyId'],
            job_id=body['jobId'],
            field=body['fieldToUpdate'],
            value=value
        )
        results.append(result)

    # Summarize results
    succeeded = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    summary = {'total': len(results), 'succeeded': len(succeeded), 'failed': len(failed)}

    # Determine overall response status
    if failed:
        if any(r.get('statusCode') == 404 for r in failed):
            status_code = 404
            success_flag = False
            message = "One or more items not found"
        else:
            status_code = 207  # Multi-Status
            success_flag = False
            message = "Some updates failed"
    else:
        status_code = 200
        success_flag = True
        message = "All updates completed successfully"

    return create_response(status_code, {
        'success': success_flag,
        'message': message,
        'results': results,
        'summary': summary
    })
