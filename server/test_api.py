import json
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


if __name__ == "__main__":
    print("Testing /ping endpoint...")
    test_ping()
    print("\nTesting /upload endpoint...")
    test_upload()
    print("\nTesting /invocations endpoint...")
    test_invocations()
