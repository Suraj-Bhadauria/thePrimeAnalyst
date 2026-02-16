# WHAT DOES THIS AGENT DO?
# - this file takes the user query and sends it to llm to get structured data
# - converting vague user query into structured data
# - then agents will work on this structured data 
# - the better we can convert user query to structured data, the more accurate analysis we can get 
# - prompt used : QUERY_UNDERSTANDING_PROMPT 

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from src.config import config
from src.utils.prompts import QUERY_UNDERSTANDING_PROMPT


# todo : find out what all metrices can be found in user's query besides these
class QueryPlan(BaseModel):
    intent: str = Field(description="Type of query intent")
    entities: Dict[str, Any] = Field(description="Extracted entities")
    metrics: List[str] = Field(description="Metrics to calculate")
    filters: List[Dict] = Field(description="Filter conditions")
    grouping: List[str] = Field(description="Grouping dimensions")
    is_followup: bool = Field(description="Whether this is a follow-up question")

class QueryUnderstandingAgent:
    def __init__(self):
        self.llm = ChatGroq(
            temperature=config.TEMPERATURE,
            model_name=config.MODEL_NAME,
            groq_api_key=config.GROQ_API_KEY
        )
        self.parser = PydanticOutputParser(pydantic_object=QueryPlan)
        
    def understand_query(self, question: str, history: str = "") -> QueryPlan:
        """Understand user query and extract structured information"""
        
        prompt = ChatPromptTemplate.from_template(
            QUERY_UNDERSTANDING_PROMPT + "\n\n{format_instructions}"
        )
        
        chain = prompt | self.llm
        
        response = chain.invoke({
            "question": question,
            "history": history,
            "format_instructions": self.parser.get_format_instructions()
        })
        
        try:
            # Parse the JSON response
            import json
            content = response.content
            
            # Try to extract JSON from markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            parsed = json.loads(content)
            return QueryPlan(**parsed)
        except Exception as e:
            print(f"Error parsing query plan: {e}")
            print(f"Response: {response.content}")
            # Return a default plan
            return QueryPlan(
                intent="descriptive",
                entities={},
                metrics=["count"],
                filters=[],
                grouping=[],
                is_followup=False
            )   