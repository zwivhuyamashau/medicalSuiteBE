import json
import boto3
from decimal import Decimal
from botocore.exceptions import ClientError

# Initialize DynamoDB resource
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('quotes')

def convert_decimals(obj):
    """Recursively convert Decimal types to float/int for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj) if '.' in str(obj) else int(obj)
    if isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_decimals(v) for v in obj]
    return obj

def lambda_handler(event, context):
    # CORS headers
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Content-Type': 'application/json'
    }

    try:
        # Scan the table to retrieve all items
        response = table.scan()

        # Convert Decimals to native types
        items = [convert_decimals(item) for item in response.get('Items', [])]

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(items)
        }

    except ClientError as e:
        print(f"DynamoDB Error: {e.response['Error']['Message']}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Database operation failed'})
        }
    except Exception as e:
        print(f"Unexpected Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': 'Internal server error'})
        }
