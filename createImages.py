import json
import boto3
import uuid
import os
from openai import OpenAI
import requests
import time
from botocore.exceptions import NoCredentialsError
from concurrent.futures import ThreadPoolExecutor

# S3 Configuration
S3_BUCKET = "mail.mysterie.co.za"
EXPIRATION = 3600  # URL expiration in seconds

# Flux API Configuration
API_URL = 'https://api.us1.bfl.ai/v1'

# Flux API Key
API_KEY = os.environ.get("FLUX_API_KEY")
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
HEADERS = {
    "accept": "application/json",
    "x-key": API_KEY,
    "Content-Type": "application/json",
}

# Initialize S3 client
s3_client = boto3.client("s3")

def generate_image_OpenAI(prompt, width=1024, height=1024):
    """ Calls DALL·E 3 to generate an image based on the prompt. """
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size=f"{width}x{height}"
        )
        return response.data[0].url  
    except Exception as e:
        print(f"Error generating image: {e}")
        return None

def generate_image_Flux(prompt, width=1024, height=768):
    """ Calls Flux API to generate an image based on the prompt. """
    try:
        response = requests.post(
            f"{API_URL}/flux-dev",
            headers=HEADERS,
            json={"prompt": prompt, "width": width, "height": height},
        )
        response.raise_for_status()
        return response.json()  # Assuming Flux returns an "id" field
    except requests.exceptions.RequestException as e:
        print(f"Error generating image: {e}")
        return None

def upload_to_s3(image_url):
    """ Downloads the generated image and uploads it to S3, returning a pre-signed URL. """
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        image_data = response.content

        filename = f"room_images/{uuid.uuid4()}.png"
        s3_client.put_object(Bucket=S3_BUCKET, Key=filename, Body=image_data, ContentType="image/png")

        return s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": filename},
            ExpiresIn=EXPIRATION
        )
    except (requests.exceptions.RequestException, NoCredentialsError) as e:
        print(f"Error uploading image: {e}")
        return None

def poll_for_result(request_id, poll_interval=0.5):
    while True:
        result = requests.get(
            f'{API_URL}/get_result',
            headers=HEADERS,
            params={'id': request_id},
        ).json()
        if result["status"] == "Ready":
            return result['result']['sample']
        time.sleep(poll_interval)

def process_image(prompt):
    """ Generates an image and uploads it to S3, returning the presigned URL. """
    request = generate_image(prompt)
    
    if request and "id" in request:
        image_url = poll_for_result(request["id"])
        if image_url:
            return upload_to_s3(image_url)
    return None

def process_image_OPEN_AI(prompt):
    """ Generates an image and uploads it to S3, returning the presigned URL. """
    URL = generate_image_OpenAI(prompt)
    
    if URL :
        return upload_to_s3(URL)
    return None

def lambda_handler(event, context):
    """ AWS Lambda handler function. """
    try:
        body = event["body"]
        prompt = body

        image_urls = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = executor.map(process_image_OPEN_AI, [prompt] * 4)

        image_urls = [url for url in results if url]

        headers = {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "PUT, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({"imageUrl": image_urls})
        }
    except Exception as e:
        print(f"Error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"})
        }
