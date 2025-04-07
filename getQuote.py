import json
import os
import logging
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal
from typing import Dict, Any

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
TABLE_NAME = "quotes"
USERS_TABLE = "users"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def check_email_doctor_search_credits(email):
    table = dynamodb.Table(USERS_TABLE)
    
    response = table.get_item(Key={'email': email})
    
    if 'Item' not in response:
        return {"exists": False, "message": "Email not found"}
    
    user_data = response['Item']
    
    # Convert Decimal to int
    quote_search_credits = int(user_data.get("quote", 0))
    
    if quote_search_credits > 0:
        return {"exists": True, "quote_search_credits": quote_search_credits, "message": "quote-search credits available"}
    
    return {"exists": True, "quote_search_credits": 0, "message": "No quote-search credits available"}

def subtract_quote_credit(email):
    table = dynamodb.Table(USERS_TABLE)
    
    try:
        response = table.update_item(
            Key={'email': email},
            UpdateExpression="SET quote = quote - :dec",
            ConditionExpression="quote > :zero",
            ExpressionAttributeValues={":dec": 1, ":zero": 0},
            ReturnValues="UPDATED_NEW"
        )
        
        # Convert Decimal to int before returning response
        updated_quote_search_credits = int(response['Attributes']['quote'])
        
        return {"success": True, "updated_quote_search_credits": updated_quote_search_credits}
    
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return {"success": False, "message": "No quote-search credits left to subtract"}
        else:
            return {"success": False, "message": "Error updating item", "error": str(e)}

def lambda_handler(event, context):
    """
    Lambda function to retrieve a quote from the DynamoDB 'quotes' table 
    based on the provided email and compNameOfferering.
    """
    try:
        email = event["queryStringParameters"]["email"]
        comp_name_offering = event["queryStringParameters"]["compNameOfferering"]

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
        
        if email_check_result["quote_search_credits"] == 0:
            return {
                "statusCode": 403,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "No Quote search credits available"})
            }

        # Access the DynamoDB table
        table = dynamodb.Table(TABLE_NAME)

        # Fetch the quote using compNameOfferering as the key
        try:
            response = table.get_item(Key={"compNameOfferering": comp_name_offering})

            if "Item" not in response:
                return {
                    "statusCode": 404,
                    "headers": {"Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": "Quote not found"})
                }

            quote_data = response["Item"]
            subtract_quote_credit(email)

            return {
                "statusCode": 200,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps(quote_data, default=str)  # Convert Decimals to string if needed
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