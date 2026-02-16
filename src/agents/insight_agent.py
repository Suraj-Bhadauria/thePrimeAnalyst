from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from src.config import config
from src.utils.prompts import INSIGHT_GENERATION_PROMPT
import json

class InsightAgent:
    def __init__(self):
        self.llm = ChatGroq(
            temperature=0.3,  # Slightly higher for creative insights
            model_name=config.MODEL_NAME,
            groq_api_key=config.GROQ_API_KEY
        )
    
    def generate_insights(self, question: str, analysis_results: dict, stats_context: dict = None) -> str:
        """Generate human-readable insights from analysis results"""
        
        prompt = ChatPromptTemplate.from_template(INSIGHT_GENERATION_PROMPT)
        
        chain = prompt | self.llm
        
        response = chain.invoke({
            "question": question,
            "results": json.dumps(analysis_results, indent=2),
            "stats_context": json.dumps(stats_context or {}, indent=2)
        })
        
        return response.content