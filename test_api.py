import requests
import json

def test_ping():
    response = requests.get("http://localhost:8080/ping")
    print("Ping Response:", response.json())
    assert response.status_code == 200

def test_invocations():
    payload = {
        "s3_urls": {
            "sales_data": "s3://your-bucket/path/to/sales_data.csv",
            "inventory_data": "s3://your-bucket/path/to/inventory.xlsx"
        },
        "prompt": "What is the total revenue for each product category?"
    }

    response = requests.post(
        "http://localhost:8080/invocations",
        json=payload,
        headers={"Content-Type": "application/json"}
    )

    print("Status Code:", response.status_code)
    print("\nResponse:")
    print(json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    print("Testing /ping endpoint...")
    test_ping()
    print("\nTesting /invocations endpoint...")
    test_invocations()
