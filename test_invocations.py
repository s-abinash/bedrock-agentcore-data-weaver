import requests
import json

def test_invocations_endpoint():
    url = "http://localhost:8080/invocations"

    payload = {
        "s3_urls": {
            "customers-1000": "s3://data-agent-bedrock-ac/customers-1000_edb6516c63ca4157a6efd4ba827b9c01.csv"
        },
        "prompt": "How many total customers we have?"
    }

    print("Testing /invocations endpoint...")
    print(f"Request payload: {json.dumps(payload, indent=2)}")

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()

        result = response.json()
        print("\n" + "="*50)
        print("SUCCESS!")
        print("="*50)
        print(f"\nResponse Status: {response.status_code}")
        print(f"\nOutput:\n{result.get('output', 'No output')}")
        print(f"\nDataframes loaded: {result.get('dataframes_loaded', [])}")
        print(f"\nIntermediate steps: {len(result.get('intermediate_steps', []))} steps")

        return result

    except requests.exceptions.ConnectionError:
        print("\nERROR: Could not connect to server. Is it running?")
        print("Start the server with: python -m server.app")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"\nHTTP ERROR: {e}")
        print(f"Response: {e.response.text}")
        return None
    except Exception as e:
        print(f"\nERROR: {e}")
        return None


if __name__ == "__main__":
    test_invocations_endpoint()
