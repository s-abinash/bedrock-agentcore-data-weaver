import json
import uuid
import requests

BASE_URL = "http://localhost:8080"


def test_ping():
    response = requests.get(f"{BASE_URL}/ping")
    print("Ping Response:", response.json())
    assert response.status_code == 200


def test_upload():
    files = {
        "files": (
            "customers.csv",
            "Name,Country\nAlice,USA\nBob,Canada\n",
            "text/csv",
        )
    }

    response = requests.post(f"{BASE_URL}/upload", files=files)
    print("Upload Status Code:", response.status_code)
    print("Upload Response:", json.dumps(response.json(), indent=2))


def test_invocations():
    payload = {
        "s3_urls": {
            "customers": "s3://data-agent-bedrock-ac/customers-1000.csv"
        },
        "prompt": "Which country our major customers are from?"
    }

    response = requests.post(
        f"{BASE_URL}/invocations",
        json=payload,
        headers={"Content-Type": "application/json"}
    )

    print("Invocation Status Code:", response.status_code)
    print("Invocation Response:", json.dumps(response.json(), indent=2))

def test_chat():
    payload = {
        "s3_urls": {
            "customers": "s3://data-agent-bedrock-ac/customers-1000.csv"
        },
        "prompt": "Generate a bar chart showing the number of customers per country and summarize the most significant insight.",
    }

    headers = {
        "Content-Type": "application/json",
        "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": uuid.uuid4().hex + uuid.uuid4().hex,
    }

    response = requests.post(
        f"{BASE_URL}/chat",
        json=payload,
        headers=headers,
    )

    print("Chat Status Code:", response.status_code)
    response_body = response.json()
    print("Chat Response:", json.dumps(response_body, indent=2))
    charts = response_body.get("charts") or []
    print("Total Charts:", len(charts))
    if charts:
        print("Chart URLs:")
        for index, chart_url in enumerate(charts, start=1):
            print(f"  {index}. {chart_url}")

if __name__ == "__main__":
    print("Testing /ping endpoint...")
    test_ping()
    # print("\nTesting /upload endpoint...")
    # test_upload()
    # print("\nTesting /invocations endpoint...")
    # test_invocations()
    print("\nTesting /chat endpoint...")
    test_chat()
