import json
import os
import logging
import requests
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal
from typing import Dict, Any

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
TABLE_NAME = "users"


logger = logging.getLogger()
logger.setLevel(logging.INFO)

GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY')
PLACES_API_BASE_URL = 'https://places.googleapis.com/v1'

def check_email_doctor_search_credits(email):
    table = dynamodb.Table(TABLE_NAME)
    
    response = table.get_item(Key={'email': email})
    
    if 'Item' not in response:
        return {"exists": False, "message": "Email not found"}
    
    user_data = response['Item']
    
    # Convert Decimal to int
    doctor_search_credits = int(user_data.get("doctor", 0))
    
    if doctor_search_credits > 0:
        return {"exists": True, "doctor_search_credits": doctor_search_credits, "message": "doctor-search credits available"}
    
    return {"exists": True, "doctor_search_credits": 0, "message": "No doctor-search credits available"}

def subtract_doctor_credit(email):
    table = dynamodb.Table(TABLE_NAME)
    
    try:
        response = table.update_item(
            Key={'email': email},
            UpdateExpression="SET doctor = doctor - :dec",
            ConditionExpression="doctor > :zero",
            ExpressionAttributeValues={":dec": 1, ":zero": 0},
            ReturnValues="UPDATED_NEW"
        )
        
        # Convert Decimal to int before returning response
        updated_doctor_search_credits= int(response['Attributes']['doctor'])
        
        return {"success": True, "updated_doctor_search_credits": updated_doctor_search_credits}
    
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return {"success": False, "message": "No doctor-search credits left to subtract"}
        else:
            return {"success": False, "message": "Error updating item", "error": str(e)}


def lambda_handler(event, context):
    print("--------")
    print(event)
    print("--------")
    """
    Main Lambda handler that processes Places API requests
    """
    try:
        email = event.get("queryStringParameters", {}).get("email")
        
        if not email:
            return {
                "statusCode": 400,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "Missing email parameter"})
            }

        # Check if the email exists and has credits
        email_check_result = check_email_doctor_search_credits(email)
        
        if not email_check_result["exists"]:
            return {
                "statusCode": 404,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "User does not exist"})
            }
        
        if email_check_result["doctor_search_credits"] == 0:
            return {
                "statusCode": 403,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "No doctor search credits available"})
            }

        body = event['body']
        if isinstance(body, str):  # If body is a string, parse it
            body = json.loads(body)
        action = body.get('action')
        params = body.get('params')

        if action == 'nearbySearch':
            return handle_nearby_search(params,email)
        else:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Invalid action specified'})
            }
    except Exception as e:
        logger.error(f'Lambda error: {str(e)}')
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Internal server error'})
        }

def handle_nearby_search(params,email) -> Dict[str, Any]:
    """
    Handle nearby search requests using Google Places API v2
    """
    try:
        location = params.get('location')
        search_type = params.get('type', 'doctor')
        radius = params.get('radius', 5000)

        url = f"https://places.googleapis.com/v1/places:searchNearby?key={GOOGLE_MAPS_API_KEY}"
        headers = {'Content-Type': 'application/json', 'X-Goog-Api-Key': GOOGLE_MAPS_API_KEY,"X-Goog-FieldMask": "*" }
        payload = {
            "includedTypes": [search_type],
            "maxResultCount": 10,
            'locationRestriction': {
                'circle': {
                    'center': {'latitude': location.get('lat'), 'longitude': location.get('lng')},
                    'radius': radius
                }
            }
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        credit_result = subtract_doctor_credit(email)

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps(data)
        }
    except requests.exceptions.RequestException as e:
        logger.error(f'Nearby search error: {str(e)}')
        return {
            'statusCode': e.response.status_code if e.response else 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Failed to search nearby places'})
        }
