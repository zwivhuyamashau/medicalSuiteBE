import json
import base64
import os
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

IMAGE_TO_TEXT_PROMPT = """
Analyze this image and provide a highly detailed breakdown of the room for reconstruction by builders. be very detailed about the room structure.
1. walls.
	referene to  where the picture was taken, 
		How many walls are there in the picture?
		what are the dimensions of the walls ?
        hor far from the camera is the rear wall ?
		how are the walls in relation to each other 
		how are are the walls in felation to the floor and ceiling

2. Doors & Entryways

    Number of doors per wall (indicate which walls contain doors).
    which wall is the door in ?
    how far from the wall corner is the Doors placed ?
    Exact placement of each door: Provide X, Y coordinates relative to the floor and nearest wall corner.
    Door dimensions: Height, width, and thickness.
    Door types: Wooden, glass, metal, sliding, French doors, panel doors, two-sided doors, etc.
    Number of door panels per door: Single-pane, double-pane, multi-section, etc.
    Door frame details: Material, color, and thickness.
    Door swing direction: Inward or outward, left or right.
    Door hardware: Handles, locks, hinges, and additional design features.

3. Windows

    Number of windows per wall (indicate which walls contain windows).
    how many walls have windows
    which wall is the Windows in?
    how far from the wall corner is the window placed ?
    Exact placement of each window per wall: Provide X, Y coordinates relative to the floor and nearest wall corner.
    Window dimensions: Height, width, and depth.
    Window types: Single-hung, double-hung, casement, bay, sliding, fixed, etc.
    Number of window panes per window.
    Frame material and color.
    Window hardware: Locks, handles, and any additional features.

4. Fixtures & Built-in Features

    Built-in shelving, cabinets, or storage: Placement, dimensions, and materials.
    Fireplaces or wall-mounted appliances: Location and dimensions.

Ensure that the output response is structured, precise, and comprehensive, making it easy for builders to replicate the room exactly as it appears in the image.

"""

dynamodb = boto3.resource('dynamodb')
TABLE_NAME = "users"

def check_email_image_credits(email):
    table = dynamodb.Table(TABLE_NAME)
    
    response = table.get_item(Key={'email': email})
    
    if 'Item' not in response:
        return {"exists": False, "message": "Email not found"}
    
    user_data = response['Item']
    
    # Convert Decimal to int
    image_credits = int(user_data.get("image", 0))
    
    if image_credits > 0:
        return {"exists": True, "image_credits": image_credits, "message": "image credits available"}
    
    return {"exists": True, "image_credits": 0, "message": "No image credits available"}

def subtract_image_credit(email):
    table = dynamodb.Table(TABLE_NAME)
    
    try:
        response = table.update_item(
            Key={'email': email},
            UpdateExpression="SET image = image - :dec",
            ConditionExpression="image > :zero",
            ExpressionAttributeValues={":dec": 1, ":zero": 0},
            ReturnValues="UPDATED_NEW"
        )
        
        # Convert Decimal to int before returning response
        updated_image_credits = int(response['Attributes']['image'])
        
        return {"success": True, "updated_image_credits": updated_image_credits}
    
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return {"success": False, "message": "No marketing credits left to subtract"}
        else:
            return {"success": False, "message": "Error updating item", "error": str(e)}

def lambda_handler(event, context):
    print(event)
    print("-------")
    """AWS Lambda function to analyze a room image from API Gateway."""
    # Parse the incoming request
    body = event["body"]
    base64_image = body
    email = event.get("queryStringParameters", {}).get("email")
        
    try:

        if not base64_image:
            return {
                "statusCode": 400,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "Missing 'image' in request body"})
            }

        if not email:
            return {
                "statusCode": 400,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "Missing email parameter"})
            }

        # Check if the email exists and has credits
        email_check_result = check_email_image_credits(email)
        
        if not email_check_result["exists"]:
            return {
                "statusCode": 404,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "User does not exist"})
            }
        
        if email_check_result["image_credits"] == 0:
            return {
                "statusCode": 403,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "No image credits available"})
            }


        # Send the image to OpenAI for analysis
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": IMAGE_TO_TEXT_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                    ],
                }
            ],
            max_tokens=700,
        )

        # Extract response content
        analysis_result = response.choices[0].message.content
        credit_result = subtract_image_credit(email)
        return {
            "statusCode": 200,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"analysis": analysis_result})
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)})
        }