# WHAT DOES THIS AGENT DO?
# - takes the structured query from query_agent and make a plan to follow 
# - prompt used : PLANNER_PROMPT

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import json
from src.config import config
from src.utils.prompts import PLANNER_PROMPT

class ExecutionPlan(BaseModel):
    filters: List[Dict] = Field(default_factory=list)
    groupby: List[str] = Field(default_factory=list)
    aggregations: List[Dict] = Field(default_factory=list)
    computations: List[Dict] = Field(default_factory=list)
    sort: Optional[Dict] = None
    limit: Optional[int] = None

class PlannerAgent:
    def __init__(self):
        self.llm = ChatGroq(
            temperature=config.TEMPERATURE,
            model_name=config.MODEL_NAME,
            groq_api_key=config.GROQ_API_KEY
        )
    
    def create_execution_plan(self, query_plan: dict) -> ExecutionPlan:
        """Create execution plan from query understanding"""
        
        prompt = ChatPromptTemplate.from_template(PLANNER_PROMPT)
        
        chain = prompt | self.llm
        
        response = chain.invoke({
            "query_plan": json.dumps(query_plan, indent=2)
        })
        
        try:
            content = response.content
            
            # Extract JSON from markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            parsed = json.loads(content)
            return ExecutionPlan(**parsed)
        except Exception as e:
            print(f"Error creating execution plan: {e}")
            print(f"Response: {response.content}")
            return ExecutionPlan()