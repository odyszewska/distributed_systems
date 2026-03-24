import os
import asyncio
import httpx
import time
import hmac
from collections import defaultdict, deque
from difflib import SequenceMatcher
from enum import Enum
from fastapi import FastAPI, HTTPException, Depends, Form, Request, status, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, ValidationError, field_validator
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Zadanie 2 - Food Comparison API")

templates = Jinja2Templates(directory="templates")

OFF_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
# OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{code}"
USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
USDA_PRODUCT_URL = "https://api.nal.usda.gov/fdc/v1/food/{fdc_id}"

HTTP_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
OFF_TIMEOUT = httpx.Timeout(25.0, connect=15.0, read=25.0)
OFF_HEADERS = {"User-Agent": "Zadanie2-FoodComparisonAPI"}

API_KEY_HEADER_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 10
rate_limit_store: dict[str, deque[float]] = defaultdict(deque)

class ComparisonCriteria(str, Enum):
    overall = "overall"
    less_calories = "less_calories"
    less_sugar = "less_sugar"
    less_salt = "less_salt"
    more_protein = "more_protein"

class ComparisonRequest(BaseModel):
    product_a: str = Field(min_length=2, max_length=100)
    product_b: str = Field(min_length=2, max_length=100)
    criteria: ComparisonCriteria = Field()

    @field_validator("product_a", "product_b")
    @classmethod
    def validate_product_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Product name cannot be empty")
        return cleaned

class ComparisonError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    return response

def get_client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"

async def verify_api_key(api_key: str | None = Depends(api_key_header)):
    expected_key = os.getenv("APP_API_KEY")
    if not expected_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="API key not configured")
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")
    if not hmac.compare_digest(api_key, expected_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

async def rate_limit_api(request: Request):
    client_ip = get_client_ip(request)
    now = time.time()
    requests = rate_limit_store[client_ip]

    while requests and now - requests[0] > RATE_LIMIT_WINDOW_SECONDS:
        requests.popleft()

    if len(requests) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded. Try again later.")

    requests.append(now)

def to_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def candidate_score(query: str, product_name: str, brand: str = "") -> float:
    query_norm = query.strip().lower()
    text = f"{product_name or ''} {brand or ''}".strip().lower()

    if not text:
        return 0.0

    score = SequenceMatcher(None, query_norm, text).ratio()

    if query_norm in text:
        score += 0.5

    for token in query_norm.split():
        if token in text:
            score += 0.1

    return score

async def safe_fetch(coro, source_name: str):
    try:
        data = await coro
        return {"data": data, "error": None}
    except httpx.ReadTimeout:
        return {"data": None, "error": ComparisonError(status_code=504, message=f"{source_name} request timed out")}
    except httpx.RequestError:
        return {"data": None, "error": ComparisonError(status_code=503, message=f"{source_name} is unavaialble")}
    except httpx.HTTPStatusError as e:
        return {"data": None, "error": ComparisonError(status_code=502, message=f"{source_name} returned {e.response.status_code}")}
    except ComparisonError as e:
        return {"data": None, "error": e}
    except Exception:
        return {"data": None, "error": ComparisonError(status_code=500, message=f"Unexpected error while processing {source_name} data")}

def first_non_none(*args):
    for arg in args:
        if arg is not None:
            return arg
    return None

def extract_off_product_data(product: dict) -> dict:
    nutriments = product.get("nutriments", {})

    name = product.get("product_name") or product.get("product_name_en") or product.get("generic_name") or product.get("generic_name_en") or "Unknown Product"
    brand = product.get("brands") or "Unknown Brand"
    return {
        "name": name,
        "brand": brand,
        "nutrition_per_100g": {
            "kcal": first_non_none(to_float(nutriments.get("energy-kcal_100g")), to_float(nutriments.get("energy-kcal"))),
            "sugar": first_non_none(to_float(nutriments.get("sugars_100g")), to_float(nutriments.get("sugars"))),
            "salt": first_non_none(to_float(nutriments.get("salt_100g")), to_float(nutriments.get("salt"))),
            "protein": first_non_none(to_float(nutriments.get("proteins_100g")), to_float(nutriments.get("proteins")))},
    }

async def fetch_off_product(client: httpx.AsyncClient, product_name: str):
    search_params = {
        "search_terms": product_name,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": 5,
        "fields": "code,product_name,product_name_en,generic_name,generic_name_en,brands,nutriments"
    }

    response = await client.get(OFF_SEARCH_URL, params=search_params, headers=OFF_HEADERS)
    response.raise_for_status()

    products = response.json().get("products", [])
    if not products:
        return None

    best_product = max(
        products,
        key=lambda p: candidate_score(product_name, p.get("product_name", ""), p.get("brands", "")),
    )

    return extract_off_product_data(best_product)

def extract_usda_product_data(product: dict) -> dict:
    nutrients = product.get("foodNutrients", [])
    kcal = None
    sugar = None
    sodium_mg = None
    protein = None

    for nutrient in nutrients:
        nutrient_info = nutrient.get("nutrient", {})
        name = (nutrient_info.get("name") or nutrient.get("nutrientName") or "").lower()
        unit = (nutrient_info.get("unitName") or nutrient.get("unitName") or "").upper()
        val = nutrient.get("amount")
        if val is None:
            val = nutrient.get("value")
        value = to_float(val)

        if value is None:
            continue

        if name == "protein":
            protein = value
        elif name == "energy" and unit == "KCAL":
            kcal = value
        elif "sugars" in name and sugar is None:
            sugar = value
        elif "sodium" in name and sodium_mg is None:
            sodium_mg = value

    salt = None
    if sodium_mg is not None:
        salt = round((sodium_mg/1000) * 2.5,2)

    return {
        "name": product.get("description") or "Unknown Product",
        "brand": product.get("brandOwner") or "Unknown Brand",
        "nutrition_per_100g": {
            "kcal": kcal,
            "sugar": sugar,
            "salt": salt,
            "protein": protein,
        }
    }

async def fetch_usda_product(client: httpx.AsyncClient, product_name: str):
    api_key = os.getenv("USDA_API_KEY")
    if not api_key:
        raise ComparisonError(status_code=500, message="USDA API key not configured")
    
    search_response = await client.get(
        USDA_SEARCH_URL,
        params={"query": product_name, "pageSize": 5, "api_key": api_key},
        headers={"User-Agent": "Zadanie2-FoodComparisonAPI"}
    )
    search_response.raise_for_status()

    foods = search_response.json().get("foods", [])
    if not foods:
        return None

    best_food = max(
        foods,
        key=lambda f: candidate_score(product_name, f.get("description", ""), f.get("brandOwner", "")),
    )

    fdc_id = best_food.get("fdcId")
    if not fdc_id:
        return None

    detail_response = await client.get(
        USDA_PRODUCT_URL.format(fdc_id=fdc_id),
        params={"api_key": api_key},
        headers={"User-Agent": "Zadanie2-FoodComparisonAPI"}
    )
    detail_response.raise_for_status()

    return extract_usda_product_data(detail_response.json())

def has_any_nutrition(data: dict) -> bool:
    nutrition = data["nutrition_per_100g"]
    return any(value is not None for value in nutrition.values())

def choose_name(query: str, off_data: dict | None, usda_data: dict | None) -> str:
    off_name = off_data.get("name") if off_data else None
    usda_name = usda_data.get("name") if usda_data else None

    if usda_name and usda_name != "Unknown Product":
        return usda_name
    if off_name and off_name != "Unknown Product":
        return off_name
    return query

def merge_product_data(query: str, off_result: dict, usda_result: dict) -> dict:
    off_data = off_result["data"]
    usda_data = usda_result["data"]

    warnings = []

    if off_result["error"] is not None:
        warnings.append(f"OFF data warning: {off_result['error'].message}")

    if usda_result["error"] is not None:
        warnings.append(f"USDA data warning: {usda_result['error'].message}")

    if off_data is None and usda_data is None:
        if off_result["error"] is not None and usda_result["error"] is not None:
            raise ComparisonError(status_code=503, message="Both OFF and USDA requests failed")
        raise ComparisonError(status_code=404, message="Product not found in both databases")
    
    matched_name = choose_name(query, off_data, usda_data)

    nutrition = {
        "kcal": None,
        "sugar": None,
        "salt": None,
        "protein": None,
    }

    for field in nutrition.keys():
        off_value = None if off_data is None else off_data["nutrition_per_100g"].get(field)
        usda_value = None if usda_data is None else usda_data["nutrition_per_100g"].get(field)

        if off_value is not None and usda_value is not None:
            nutrition[field] = round((off_value + usda_value) / 2, 2)
        elif off_value is not None:
            nutrition[field] = off_value
        elif usda_value is not None:
            nutrition[field] = usda_value

    merged = {
        "query": query,
        "name": matched_name,
        "nutrition_per_100g": nutrition,
        "warnings": warnings
    }

    if not has_any_nutrition(merged):
        raise ComparisonError(status_code=404, message="No nutritional information found for the product")
    
    return merged   

def compare_products(prod_a: dict, prod_b: dict, criteria: ComparisonCriteria) -> dict:
    a = prod_a["nutrition_per_100g"]
    b = prod_b["nutrition_per_100g"]

    if criteria == ComparisonCriteria.less_calories:
        field_name = "kcal"
        label = "calories"
        lower_is_better = True
    elif criteria == ComparisonCriteria.less_sugar:
        field_name = "sugar"
        label = "sugar"
        lower_is_better = True
    elif criteria == ComparisonCriteria.less_salt:
        field_name = "salt"
        label = "salt"
        lower_is_better = True
    elif criteria == ComparisonCriteria.more_protein:
        field_name = "protein"
        label = "protein"
        lower_is_better = False
    else:
        score_a = 0
        score_b = 0
        details = []

        if a.get("kcal") is not None and b.get("kcal") is not None:
            if a["kcal"] < b["kcal"]:
                score_a += 1
                details.append(f"{prod_a['name']} has fewer calories than {prod_b['name']}.")
            elif a["kcal"] > b["kcal"]:
                score_b += 1
                details.append(f"{prod_b['name']} has fewer calories than {prod_a['name']}.")

        if a.get("sugar") is not None and b.get("sugar") is not None:
            if a["sugar"] < b["sugar"]:
                score_a += 1
                details.append(f"{prod_a['name']} has less sugar than {prod_b['name']}.")
            elif a["sugar"] > b["sugar"]:
                score_b += 1
                details.append(f"{prod_b['name']} has less sugar than {prod_a['name']}.")

        if a.get("salt") is not None and b.get("salt") is not None:
            if a["salt"] < b["salt"]:
                score_a += 1
                details.append(f"{prod_a['name']} has less salt than {prod_b['name']}.")
            elif a["salt"] > b["salt"]:
                score_b += 1
                details.append(f"{prod_b['name']} has less salt than {prod_a['name']}.")

        if a.get("protein") is not None and b.get("protein") is not None:
            if a["protein"] > b["protein"]:
                score_a += 1
                details.append(f"{prod_a['name']} has more protein than {prod_b['name']}.")
            elif a["protein"] < b["protein"]:
                score_b += 1
                details.append(f"{prod_b['name']} has more protein than {prod_a['name']}.")

        if score_a == score_b:
            winner = "tie"
            explanation = "Both products have the same overall score."
        elif score_a > score_b:
            winner = prod_a["name"]
            explanation = f"{prod_a['name']} has a higher overall score."
        else:
            winner = prod_b["name"]
            explanation = f"{prod_b['name']} has a higher overall score."

        return {
            "criteria": criteria.value,
            "winner": winner,
            "explanation": explanation,
            "scores": {
                "product_a_score": score_a,
                "product_b_score": score_b,
                "details": details
            }
        }

    value_a = a.get(field_name)
    value_b = b.get(field_name)

    if value_a is None and value_b is None:
        raise ComparisonError(status_code=404, message=f"No {label} information found for either product")

    if value_a is None or value_b is None:
        missing = []
        if value_a is None:
            missing.append(prod_a["name"])
        if value_b is None:
            missing.append(prod_b["name"])
        raise ComparisonError(status_code=404, message=f"No {label} information found for: {', '.join(missing)}")
    
    if value_a == value_b:
        winner = "tie"
        explanation = f"Both products have the same {label} value."
    else:
        if lower_is_better:
            winner = prod_a["name"] if value_a < value_b else prod_b["name"]
            loser = prod_b["name"] if value_a < value_b else prod_a["name"]
            explanation = f"{winner} has less {label} than {loser}."
        else:
            winner = prod_a["name"] if value_a > value_b else prod_b["name"]
            loser = prod_b["name"] if value_a > value_b else prod_a["name"]
            explanation = f"{winner} has more {label} than {loser}."
    
    return {
        "criteria": criteria.value,
        "winner": winner,
        "explanation": explanation,
        "values": {
            "product_a_value": round(value_a, 2),
            "product_b_value": round(value_b, 2),
            "difference": round(abs(value_a - value_b), 2),
            "unit": "g" if field_name != "kcal" else "kcal"
        }
    }



async def run_comparison(payload: ComparisonRequest) -> dict:
    async with httpx.AsyncClient(timeout=OFF_TIMEOUT) as off_client, httpx.AsyncClient(timeout=HTTP_TIMEOUT) as usda_client:
        results = await asyncio.gather(
            safe_fetch(fetch_off_product(off_client, payload.product_a), "OFF"),
            safe_fetch(fetch_usda_product(usda_client, payload.product_a), "USDA"),
            safe_fetch(fetch_off_product(off_client, payload.product_b), "OFF"),
            safe_fetch(fetch_usda_product(usda_client, payload.product_b), "USDA")
        )

    prod_a_off, prod_a_usda, prod_b_off, prod_b_usda = results
    
    prod_a = merge_product_data(payload.product_a, prod_a_off, prod_a_usda)
    prod_b = merge_product_data(payload.product_b, prod_b_off, prod_b_usda)

    comparison = compare_products(prod_a, prod_b, payload.criteria)

    return {
        "product_a": prod_a,
        "product_b": prod_b,
        **comparison,
    }



@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def get_index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={})

@app.get("/api/v1/comparisons", dependencies=[Depends(verify_api_key), Depends(rate_limit_api)])
async def get_comparison(
    product_a: str = Query(..., min_length=2, max_length=100),
    product_b: str = Query(..., min_length=2, max_length=100),
    criteria: ComparisonCriteria = Query(...)):
    try:
        payload = ComparisonRequest(product_a=product_a, product_b=product_b, criteria=criteria)
        return await run_comparison(payload)
    except ComparisonError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    
@app.get("/ui/compare", response_class=HTMLResponse, include_in_schema=False)
async def compare_from_form(
    request: Request,
    product_a: str = Query(..., min_length=2, max_length=100),
    product_b: str = Query(..., min_length=2, max_length=100),
    criteria: ComparisonCriteria = Query(...),
):
    try:
        payload = ComparisonRequest(product_a=product_a, product_b=product_b, criteria=criteria)
        result = await run_comparison(payload)
        return templates.TemplateResponse(request=request, name="result.html", context={ "error": None,"result": result})
    except ComparisonError as e:
        return templates.TemplateResponse(request=request, name="result.html", context={ "error": e.message,"result": None}, status_code=e.status_code)
    except ValidationError as e:
        error_messages = [err["msg"] for err in e.errors()]
        return templates.TemplateResponse(
            request=request,
            name="result.html",
            context={"error": "Invalid input: " + ", ".join(error_messages), "result": None},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except Exception:
        return templates.TemplateResponse(request=request, name="result.html", context={ "error": f"Unexpected server error","result": None}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
