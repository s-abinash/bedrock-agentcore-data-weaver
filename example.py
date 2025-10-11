import os
import pandas as pd
from langchain_openai import ChatOpenAI
from data_analyzer import analyze_data

def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Please set OPENAI_API_KEY environment variable")
        return

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=api_key
    )

    sample_data = {
        'Product': ['Laptop', 'Mouse', 'Keyboard', 'Monitor', 'Headphones'],
        'Category': ['Electronics', 'Accessories', 'Accessories', 'Electronics', 'Accessories'],
        'Price': [999.99, 24.99, 79.99, 449.99, 149.99],
        'Sales': [150, 320, 210, 95, 180],
        'Rating': [4.5, 4.2, 4.6, 4.8, 4.3]
    }
    df = pd.DataFrame(sample_data)

    dataframes = {'sales_data': df}

    prompt = """
    Analyze the sales data and provide the following:
    1. Which product has the highest revenue (price * sales)?
    2. What is the average rating by category?
    3. Which product category generates more total revenue?

    Present the results in a clear markdown format.
    """

    print("Running analysis...")
    print("-" * 50)

    result = analyze_data(dataframes, llm, prompt)

    print("\nAnalysis Result:")
    print("-" * 50)
    print(result['output'])

if __name__ == "__main__":
    main()
