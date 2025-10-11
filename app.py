import json
import os
from flask import Flask, request, jsonify, Response
from langchain_aws import ChatBedrock
from data_analyzer import analyze_data
from s3_loader import load_from_s3, load_multiple_from_s3
import pandas as pd
import traceback
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

def get_bedrock_llm():
    return ChatBedrock(
        model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
        region_name=os.environ.get("AWS_REGION", "us-east-1")
    )

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "Healthy"})

@app.route('/invocations', methods=['POST'])
def invocations():
    try:
        event = request.get_json()

        s3_urls = event.get('s3_urls', {})
        prompt = event.get('prompt', '')

        if not s3_urls:
            return jsonify({
                "error": "No S3 URLs provided. Expected 's3_urls' field with dict of name->S3 URL"
            }), 400

        if not prompt:
            return jsonify({
                "error": "No prompt provided"
            }), 400

        df_dict = load_multiple_from_s3(s3_urls)

        if not df_dict:
            return jsonify({
                "error": "No dataframes loaded from S3"
            }), 400

        llm = get_bedrock_llm()

        result = analyze_data(df_dict, llm, prompt)

        return jsonify({
            "output": result.get('output', ''),
            "intermediate_steps": result.get('intermediate_steps', []),
            "dataframes_loaded": list(df_dict.keys())
        })

    except Exception as e:
        app.logger.error(f"Error processing request: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
