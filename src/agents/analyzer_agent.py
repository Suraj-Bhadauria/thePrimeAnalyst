# Fixed: Now actually executes tools instead of just binding them
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from src.config import config
from src.tools.data_tools import create_data_query_tool
from src.tools.stats_tools import create_stats_tool
import json

class AnalyzerAgent:
    def __init__(self):
        # Create tool instances
        self.data_tool = create_data_query_tool()
        self.stats_tool = create_stats_tool()
        
        self.tools = [self.data_tool, self.stats_tool]
        
        # Create a lookup dict for tool execution
        self.tool_map = {
            "query_transaction_data": self.data_tool,
            "statistical_analysis": self.stats_tool
        }

        self.llm = ChatGroq(
            temperature=config.TEMPERATURE,
            model_name=config.MODEL_NAME,
            groq_api_key=config.GROQ_API_KEY
        ).bind_tools(self.tools)
    
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert data analyst.

You are given a structured execution plan.
Use the appropriate tools to execute the plan.
Return the final results clearly.

Available tools:
- query_transaction_data: Execute queries on transaction data. Input: execution_plan (JSON string with filters, groupby, aggregations, sort, limit)
- statistical_analysis: Perform statistical analysis. Input: analysis_type (failure_rate, fraud_rate, correlation, distribution, comparison) and parameters (JSON string)
"""),
            ("human", "{input}")
        ])

        self.chain = self.prompt | self.llm

    def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """Execute a tool and return its result"""
        if tool_name not in self.tool_map:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        
        tool = self.tool_map[tool_name]
        try:
            # Invoke the tool with its arguments
            result = tool.invoke(tool_args)
            return result
        except Exception as e:
            return json.dumps({"error": str(e)})

    def analyze(self, execution_plan: dict):
        """Execute analysis based on execution plan"""

        input_text = f"""
Execute this analysis plan:

{json.dumps(execution_plan, indent=2)}

Use the query_transaction_data tool with the execution_plan as a JSON string.
"""

        # First LLM call - may request tool calls
        result = self.chain.invoke({"input": input_text})
        
        # Check if LLM wants to call tools
        if hasattr(result, 'tool_calls') and result.tool_calls:
            # Store all tool results
            all_tool_results = []
            
            for tool_call in result.tool_calls:
                tool_name = tool_call['name']
                tool_args = tool_call['args']
                
                print(f"  ⚙️ Executing tool: {tool_name}")
                
                # Actually execute the tool
                tool_result = self._execute_tool(tool_name, tool_args)
                all_tool_results.append({
                    "tool": tool_name,
                    "result": tool_result
                })
            
            # Return the actual tool execution results
            return {
                "tool_calls": len(all_tool_results),
                "results": all_tool_results
            }
        
        # If no tool calls, return the content (fallback)
        if hasattr(result, 'content') and result.content:
            return {"response": result.content}
        
        return {"error": "No results generated"}