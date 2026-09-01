import time, json, sys
from playwright.sync_api import sync_playwright

def run_steps(iteration=1):
    steps = []
    with sync_playwright() as p:
        request_context = p.request.new_context()

        # Step: GET products list
        start = time.time()
        response = request_context.get("https://automationexercise.com/api/productsList")
        end = time.time()

        steps.append({
            "Step": "15_GET products list",
            "Iteration": iteration,
            "Response Time (s)": round(end - start, 2),
            "HTTP Code": response.status
        })

        request_context.dispose()
    return steps

if __name__ == "__main__":
    # Read iterations from command line argument (default = 1)
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    all_results = []
    for i in range(1, iterations + 1):
        all_results.extend(run_steps(iteration=i))

    # Final JSON output for Streamlit
    print(json.dumps(all_results, indent=2))
