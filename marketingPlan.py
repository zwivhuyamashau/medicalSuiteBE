import json
import os
import logging
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal
from typing import Dict, Any
import uuid
from openai import OpenAI
import requests
import time

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
USERS_TABLE = "users"

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def check_email_doctor_search_credits(email):
    table = dynamodb.Table(USERS_TABLE)
    response = table.get_item(Key={'email': email})
    
    if 'Item' not in response:
        return {"exists": False, "message": "Email not found"}
    
    user_data = response['Item']
    marketing_search_credits = int(user_data.get("marketing", 0))  # Convert Decimal to int
    
    if marketing_search_credits > 0:
        return {"exists": True, "marketing_search_credits": marketing_search_credits, "message": "Marketing-search credits available"}
    
    return {"exists": True, "marketing_search_credits": 0, "message": "No marketing-search credits available"}

def subtract_marketing_credit(email):
    table = dynamodb.Table(USERS_TABLE)
    
    try:
        response = table.update_item(
            Key={'email': email},
            UpdateExpression="SET marketing = marketing - :dec",
            ConditionExpression="marketing > :zero",
            ExpressionAttributeValues={":dec": 1, ":zero": 0},
            ReturnValues="UPDATED_NEW"
        )
        
        updated_marketing_search_credits = int(response['Attributes']['marketing'])  # Convert Decimal to int before returning response
        return {"success": True, "updated_marketing_search_credits": updated_marketing_search_credits}
    
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return {"success": False, "message": "No marketing-search credits left to subtract"}
        else:
            return {"success": False, "message": "Error updating item", "error": str(e)}

def lambda_handler(event, context):
    print(event)
    print(event.get("body", "No body"))
    """
    Lambda function to retrieve a marketing from the DynamoDB 'marketings' table 
    based on the provided email and compNameOfferering.
    """
    try:
        email = event["queryStringParameters"].get("email")
        comp_name_offering = event["queryStringParameters"].get("compNameOfferering")
        
        if not email:
            return {
                "statusCode": 400,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "Missing email parameter"})
            }
        
        email_check_result = check_email_doctor_search_credits(email)  # Check if the email exists and has credits
        
        if not email_check_result["exists"]:
            return {
                "statusCode": 404,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "User does not exist"})
            }
        
        if email_check_result["marketing_search_credits"] == 0:
            return {
                "statusCode": 403,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "No marketing search credits available"})
            }
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": event["body"]
                }
            ],
            max_tokens=1000,
        )
        
        analysis_result = response.choices[0].message.content  # Extract response content
        subtract_marketing_credit(email)
        print(json.dumps(analysis_result))
        return {
            "statusCode": 200,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": analysis_result
        }
    
    except ClientError as e:
        logger.error(f"DynamoDB error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Failed to retrieve data from database"})
        }
    
    except Exception as e:
        logger.error(f"Lambda error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Internal server error"})
        }
