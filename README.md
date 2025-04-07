# medicalSuiteBE

This is a collection of my backend code that goes to AWS lambda functions and API gateway.# MEDICALSUITEBE

This project is a backend suite designed for a medical application. It consists of multiple AWS Lambda functions that provide image handling, quote management, user details, and location-based functionalities. The API is defined and managed via an OpenAPI 3.0 specification file.

---

## 📘 API Gateway

**File:** `APIGatewayOpenAPI3.json`  
Defines the structure and endpoints of the REST API using OpenAPI 3.0 specification. It maps HTTP requests to Lambda integrations and outlines input/output schemas, security, and available paths.

---

## 🧠 Lambda Functions

### 1. `createImages.py`

---

### 2. `getQuote.py`

---

### 3. `getQuotes.py`

---

### 4. `getUserDetails.py`

---

### 5. `marketingPlan.py`

---

### 6. `places.py`

---

### 7. `readImage.py`

---

## 📄 README.md

---

## 🛠️ Deployment Notes

- **Language:** Python (all Lambda functions)
- **Deployment Target:** AWS Lambda + API Gateway
- **API Definition:** OpenAPI 3.0
- **IAM Permissions:** Each function should have the necessary execution roles and permissions to access logs, S3 (for images), or DynamoDB (for quotes/users).
