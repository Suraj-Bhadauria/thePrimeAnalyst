# THIS IS THE MAIN ORCHESTRATION WORKFLOW FOR ALL AGENTS
# - it defines the flow how the pre-defined agents work together

from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
import json

from src.agents.query_agent import QueryUnderstandingAgent
from src.agents.planner_agent import PlannerAgent
from src.agents.analyzer_agent import AnalyzerAgent
from src.agents.insight_agent import InsightAgent

# SHARED STATE
# this is the common state which will be shared by all the agents to work together
class AgentState(TypedDict):
    question: str
    conversation_history: list
    query_plan: dict
    execution_plan: dict
    analysis_results: dict
    final_response: str
    error: str

class Workflow:
    # initializing the 4 agents in constructor 
    def __init__(self):
        self.query_agent = QueryUnderstandingAgent()
        self.planner_agent = PlannerAgent()
        self.analyzer_agent = AnalyzerAgent()
        self.insight_agent = InsightAgent()
        
        # Build the graph
        self.workflow = self._build_workflow()
    
    def _build_workflow(self):
        """Build the LangGraph workflow"""
        
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("understand_query", self.understand_query)
        workflow.add_node("create_plan", self.create_plan)
        workflow.add_node("analyze_data", self.analyze_data)
        workflow.add_node("generate_insights", self.generate_insights)
        
        # Add edges
        workflow.set_entry_point("understand_query")
        workflow.add_edge("understand_query", "create_plan")
        workflow.add_edge("create_plan", "analyze_data")
        workflow.add_edge("analyze_data", "generate_insights")
        workflow.add_edge("generate_insights", END)
        
        return workflow.compile()
    
    def understand_query(self, state: AgentState) -> AgentState:
        """Step 1: Understand the query"""
        print("\n🔍 Step 1: Understanding query...")
        
        try:
            history = "\n".join([
                f"Q: {msg['question']}\nA: {msg['response']}"
                for msg in state.get('conversation_history', [])[-3:]
            ])
            
            query_plan = self.query_agent.understand_query(
                state['question'],
                history
            )
            
            state['query_plan'] = query_plan.model_dump()
            print(f"✓ Query understood: Intent={query_plan.intent}")
            
        except Exception as e:
            state['error'] = f"Query understanding failed: {str(e)}"
            print(f"✗ Error: {state['error']}")
        
        return state
    
    def create_plan(self, state: AgentState) -> AgentState:
        """Step 2: Create execution plan"""
        print("\n📋 Step 2: Creating execution plan...")
        
        try:
            execution_plan = self.planner_agent.create_execution_plan(
                state['query_plan']
            )
            
            state['execution_plan'] = execution_plan.dict()
            print(f"✓ Execution plan created")
            print(f"  Filters: {len(execution_plan.filters)}")
            print(f"  Grouping: {execution_plan.groupby}")
            print(f"  Aggregations: {len(execution_plan.aggregations)}")
            
        except Exception as e:
            state['error'] = f"Planning failed: {str(e)}"
            print(f"✗ Error: {state['error']}")
        
        return state
    
    def analyze_data(self, state: AgentState) -> AgentState:
        """Step 3: Analyze data"""
        print("\n📊 Step 3: Analyzing data...")
        
        try:
            results = self.analyzer_agent.analyze(state['execution_plan'])
            state['analysis_results'] = results
            print(f"✓ Analysis completed")
            
        except Exception as e:
            state['error'] = f"Analysis failed: {str(e)}"
            print(f"✗ Error: {state['error']}")
        
        return state
    
    def generate_insights(self, state: AgentState) -> AgentState:
        """Step 4: Generate insights"""
        print("\n💡 Step 4: Generating insights...")
        
        try:
            insights = self.insight_agent.generate_insights(
                state['question'],
                state['analysis_results']
            )
            
            state['final_response'] = insights
            print(f"✓ Insights generated")
            
        except Exception as e:
            state['error'] = f"Insight generation failed: {str(e)}"
            state['final_response'] = "I encountered an error generating insights. Please try rephrasing your question."
            print(f"✗ Error: {state['error']}")
        
        return state
    
    def run(self, question: str, conversation_history: list = None) -> str:
        """Run the complete workflow"""
        
        initial_state = {
            "question": question,
            "conversation_history": conversation_history or [],
            "query_plan": {},
            "execution_plan": {},
            "analysis_results": {},
            "final_response": "",
            "error": ""
        }
        
        print(f"\n{'='*60}")
        print(f"💬 Question: {question}")
        print(f"{'='*60}")
        
        final_state = self.workflow.invoke(initial_state)
        
        if final_state.get('error'):
            print(f"\n⚠️ Workflow completed with errors")
        else:
            print(f"\n✅ Workflow completed successfully")
        
        return final_state['final_response']