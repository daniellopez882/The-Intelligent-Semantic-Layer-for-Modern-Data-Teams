from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import sqlalchemy
from typing import Optional, List, Any
import pandas as pd

class SQLQueryInput(BaseModel):
    """Input for SQL Query Tool"""
    query: str = Field(description="SQL query to execute")

class SafeSQLExecutor(BaseTool):
    name: str = "sql_executor"
    description: str = """
    Execute SQL SELECT queries on the database.
    
    IMPORTANT RULES:
    - Only SELECT queries are allowed
    - Queries are automatically limited to 100 rows
    - Use this when you need to retrieve data
    - Input must be a valid SQL SELECT statement
    
    Example: SELECT * FROM customers WHERE country = 'USA'
    """
    args_schema: Any = SQLQueryInput
    db_uri: str = Field(description="Database URI")
    
    def _run(self, query: str) -> str:
        """Execute SQL query safely"""
        try:
            # Validate query
            if not self._is_safe_query(query):
                return "Error: Only SELECT queries are allowed for safety. Mutation queries (UPDATE, DELETE, etc.) are strictly forbidden."
            
            # Add LIMIT if not present
            query = self._add_limit(query)
            
            # Execute with timeout
            engine = sqlalchemy.create_engine(self.db_uri)
            with engine.connect() as conn:
                # Use pandas for easy formatting
                df = pd.read_sql(sqlalchemy.text(query), conn)
                
                if df.empty:
                    return "Query executed successfully. No results found."
                
                # Format results
                return self._format_results(df)
                
        except Exception as e:
            return f"Error executing query: {str(e)}"
    
    def _is_safe_query(self, query: str) -> bool:
        """Check if query is safe to execute"""
        query_upper = query.strip().upper()
        
        # Must be SELECT
        if not query_upper.startswith('SELECT') and not query_upper.startswith('WITH'):
            return False
        
        # Check for dangerous keywords
        dangerous = ['DELETE', 'DROP', 'TRUNCATE', 'UPDATE', 
                    'INSERT', 'ALTER', 'CREATE', 'EXEC', 'GRANT', 'REVOKE']
        
        return not any(keyword in query_upper for keyword in dangerous)
    
    def _add_limit(self, query: str) -> str:
        """Add LIMIT clause if not present"""
        query = query.rstrip('; \n')
        if 'LIMIT' not in query.upper():
            query += ' LIMIT 100'
        return query
    
    def _format_results(self, df: pd.DataFrame) -> str:
        """Format query results as readable text"""
        rows_count = len(df)
        result = f"Found {rows_count} row(s)\n\n"
        
        # Use pandas string representation for a nice table
        result += df.to_string(index=False)
        
        return result

class QueryComplexityAnalyzer(BaseTool):
    name: str = "query_analyzer"
    description: str = "Analyze a SQL query for complexity and potential performance issues."
    
    def _run(self, query: str) -> str:
        complexity_score = 0
        issues = []
        
        query_upper = query.upper()
        
        # Count JOINS
        joins_count = query_upper.count("JOIN")
        complexity_score += joins_count * 2
        if joins_count > 3:
            issues.append(f"High number of joins ({joins_count}). May be slow.")
            
        # Check for SELECT *
        if "SELECT *" in query_upper:
            complexity_score += 1
            issues.append("Using SELECT *. Consider selecting only necessary columns.")
            
        # Check for subqueries
        subqueries_count = query_upper.count("(SELECT")
        complexity_score += subqueries_count * 3
        if subqueries_count > 1:
            issues.append(f"Multiple subqueries detected ({subqueries_count}).")
            
        # Check for GROUP BY
        if "GROUP BY" in query_upper:
            complexity_score += 1
            
        status = "Simple" if complexity_score < 5 else "Moderate" if complexity_score < 10 else "Complex"
        
        return f"Complexity Score: {complexity_score}\nStatus: {status}\nIssues: {', '.join(issues) if issues else 'None'}"

class SchemaInspector(BaseTool):
    name: str = "schema_inspector"
    description: str = "Get the schema information for the database, including tables, columns, and sample rows."
    db_uri: str = Field(description="Database URI")

    def _run(self, query: str = "") -> str:
        from langchain_community.utilities import SQLDatabase
        db = SQLDatabase.from_uri(self.db_uri, sample_rows_in_table_info=2)
        return db.get_table_info()
