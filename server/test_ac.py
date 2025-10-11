import boto3
import json


def main():
    client = boto3.client('bedrock-agentcore', region_name='us-west-2')
    payload = json.dumps({
        "s3_urls": {"customers-1000": "s3://data-agent-bedrock-ac/customers-1000_edb6516c63ca4157a6efd4ba827b9c01.csv"},
        "prompt": "How many total customers we have?"
    }
    )

    response = client.invoke_agent_runtime(
        agentRuntimeArn='arn:aws:bedrock-agentcore:us-west-2:683883881884:runtime/data_agent_ac-kUWgSj5TwD',
        runtimeSessionId='dfmeoagmreaklgmrkleafremoigrmtesogmtrskhmtkrlsasda',
        payload=payload,
        qualifier="DEFAULT"
    )
    response_body = response['response'].read()
    response_data = json.loads(response_body)
    print("Agent Response:", response_data)


if __name__ == "__main__":
    main()
