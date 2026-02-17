# from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from src.config import config
from src.tools.data_tools import create_data_query_tool
from src.tools.stats_tools import create_stats_tool
import json

class AnalyzerAgent:
    def __init__(self):
        self.tools = [
            create_data_query_tool(),
            create_stats_tool()
        ]


        self.llm = ChatGroq(
            temperature=config.TEMPERATURE,
            model_name=config.MODEL_NAME,
            groq_api_key=config.GROQ_API_KEY
        ).bind_tools(self.tools)
    
        
#         

        
        # 3️⃣ Create prompt (NO scratchpad needed)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a data analysis agent.

You are given a structured execution plan.
Use the appropriate tools to execute the plan.
Return the final results clearly.

Available tools:
- query_transaction_data
- statistical_analysis
"""),
            ("human", "{input}")
        ])
        


        self.chain = self.prompt | self.llm

    def analyze(self, execution_plan: dict):
        """Execute analysis based on execution plan"""

        input_text = f"""
            Execute this analysis plan:

            {json.dumps(execution_plan, indent=2)}

            Use the appropriate tool(s) and return the final result.
            """

        result = self.chain.invoke({"input": input_text})

        # Extract content from AIMessage to make it JSON serializable
        if hasattr(result, 'content'):
            return {"response": result.content}
        return result