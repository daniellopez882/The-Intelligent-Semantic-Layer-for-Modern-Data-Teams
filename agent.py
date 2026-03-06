import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent, SQLDatabaseToolkit
from langchain_core.prompts import ChatPromptTemplate
from tools import SafeSQLExecutor

load_dotenv()

CUSTOM_SYSTEM_PROMPT = """You are Daniel, an advanced expert SQL data analyst.
Your goal is to provide deep insights from the database using natural language and precise SQL.

CRITICAL GUIDELINES:
1. SCHEMA AWARENESS: Always inspect the schema before writing queries. Use exact table and column names.
2. JOIN LOGIC: Prefer explicit JOINs. Ensure you connect foreign keys correctly (e.g., orders.product_id = products.product_id).
3. ANALYTICAL DEPTH: When asked for "top" or "trends", use ORDER BY and appropriate date groupings.
4. SAFETY: Never generate any queries that modify data (UPDATE, DELETE, DROP, etc.). Only SELECT is allowed.
5. EXPLANATION: After providing results, briefly explain the business significance of the data.
6. CLARITY: If a question is ambiguous, choose the most logical business interpretation but state your assumption.

TONE: Professional, insightful, and data-driven.
"""

class SQLQueryAgent:
    """Enterprise SQL Agent powered by DeepSeek and specialized reasoning"""
    
    def __init__(self, database_uri: str, api_key: str = None):
        if not api_key:
            api_key = os.getenv("DEEPSEEK_API_KEY")
            
        if not api_key:
            raise ValueError("DeepSeek API key is required. Set DEEPSEEK_API_KEY env var.")

        self.db = SQLDatabase.from_uri(
            database_uri,
            sample_rows_in_table_info=3
        )
        
        # DeepSeek V3 - Highly capable for code/SQL
        self.llm = ChatOpenAI(
            model="deepseek-chat", 
            openai_api_key=api_key,
            openai_api_base="https://api.deepseek.com/v1",
            temperature=0,
            model_kwargs={"top_p": 0.1}
        )
        
        self.toolkit = SQLDatabaseToolkit(
            db=self.db,
            llm=self.llm
        )
        
        # Local history for conversational context
        self.history = []

        # Setup the agent with standard reasoning loop
        self.agent = create_sql_agent(
            llm=self.llm,
            toolkit=self.toolkit,
            agent_type="zero-shot-react-description",
            verbose=True,
            handle_parsing_errors=True
        )
    
    def query(self, question: str) -> dict:
        """Process a natural language question with conversation memory"""
        try:
            # Pre-audit safety check
            if self._is_potentially_malicious(question):
                return {
                    "success": False,
                    "error": "Query contains forbidden keywords (DELETE, DROP, etc.). Access Denied."
                }

            # Prepare context-aware prompt
            full_input = question
            if self.history:
                history_text = "\n".join([f"Q: {h['q']}\nA: {h['a']}" for h in self.history[-3:]])
                full_input = f"Recent History:\n{history_text}\n\nCurrent Question: {question}"

            # Execute reasoning chain
            result = self.agent.invoke({
                "input": full_input
            })

            # Update history
            self.history.append({"q": question, "a": result["output"]})
            if len(self.history) > 5:
                self.history.pop(0)
            
            return {
                "success": True,
                "answer": result["output"],
                "steps": result.get("intermediate_steps", [])
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Intelligence Parse Failure: {str(e)}"
            }

    def _is_potentially_malicious(self, question: str) -> bool:
        forbidden = ["delete", "drop", "truncate", "update", "insert", "alter", "grant", "revoke"]
        return any(f in question.lower() for f in forbidden)

    def get_schema(self) -> str:
        """Fetch the technical map of the knowledge base"""
        return self.db.get_table_info()
