import json
import boto3
from decimal import Decimal
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('users')

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
        email = event.get("queryStringParameters", {}).get("email")
        
        if not email:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Email parameter is required'})
            }

        # Get item from DynamoDB
        response = table.get_item(Key={'email': email})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({'error': 'User not found'})
            }

        # Convert Decimals to native types
        item = convert_decimals(response['Item'])

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(item)
        }

    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': headers,
            'body': json.dumps({'error': 'Invalid JSON format in request body'})
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