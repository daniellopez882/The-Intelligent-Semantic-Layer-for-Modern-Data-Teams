from agent import SQLQueryAgent
from setup_db import create_sample_database
import os
from dotenv import load_dotenv

load_dotenv()

def test_agent():
    db_path = "ecommerce.db"
    db_uri = f"sqlite:///{db_path}"
    
    if not os.path.exists(db_path):
        create_sample_database(db_path)
        
    try:
        agent = SQLQueryAgent(db_uri)
        print("Schema Information:")
        print(agent.get_schema())
        print("-" * 50)
        
        question = "How many customers do we have in total?"
        print(f"Question: {question}")
        result = agent.query(question)
        
        if result["success"]:
            print(f"Answer: {result['answer']}")
        else:
            print(f"Error: {result['error']}")
            
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    test_agent()
