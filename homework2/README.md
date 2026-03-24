# Food Comparison API

A simple FastAPI application for comparing two food products by nutritional values.

The app:
- compares two products using data from **Open Food Facts** and **USDA FoodData Central**
- exposes a REST API endpoint
- includes a simple HTML form UI
- supports comparison by:
  - overall
  - less calories
  - less sugar
  - less salt
  - more protein

## Features

- FastAPI backend
- product comparison based on nutrition per 100g
- API key protection for the main API endpoint
- basic rate limiting
- HTML interface for quick testing
- Postman collection included for API tests

## Project files

- `main.py` – main FastAPI application
- `templates/index.html` – input form
- `templates/result.html` – comparison result page
- `.env` – environment variables
- `Food Comparison API.postman_collection.json` – example API requests

## Requirements

Install dependencies first:

```bash
pip install fastapi uvicorn httpx python-dotenv jinja2
```
## Environment variables

You must generate your USDA key and put it into the .env file as USDA_API_KEY

## How to run

Start the server with:

```bash
uvicorn main:app --reload
Available URLs
```

After starting the app, it will be available at:

- UI: http://127.0.0.1:8000/
- API: http://127.0.0.1:8000/api/v1/comparisons
  

### Example API request

```http
GET /api/v1/comparisons?product_a=Almond butter&product_b=Peanut butter&criteria=overall
X-API-Key: APP_API_KEY
```
