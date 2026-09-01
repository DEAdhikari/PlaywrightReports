# Day07_ApiGetProductsScript.py
import time
import json
from playwright.sync_api import sync_playwright

def run_steps():
    steps = []
    with sync_playwright() as p:
        request_context = p.request.new_context()

        # Step: GET products list (with timing)
        start = time.time()
        response = request_context.get("https://automationexercise.com/api/productsList")
        end = time.time()
        steps.append({"Step": "07_GET products list", "Response Time (s)": round(end - start, 2)})

        # Basic validation (no timing recorded)
        if response.status != 200:
            print(f"❌ GET call failed with status {response.status}")
        else:
            data = response.json()
            if "products" in data and isinstance(data["products"], list) and len(data["products"]) > 0:
                print("✅ Products list retrieved successfully")
                print("First product:", data["products"][0]["name"])
            else:
                print("❌ Invalid products list in response")

        request_context.dispose()
    return steps

if __name__ == "__main__":
    steps = run_steps()
    # Print JSON so Streamlit or logs can parse easily
    print(json.dumps(steps, indent=2))
