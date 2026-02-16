from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
import pandas as pd
import json
from typing import Any, Dict, List
from src.utils.data_loader import data_loader

class QueryDataInput(BaseModel):
    execution_plan: str = Field(description="JSON string containing the execution plan with filters, groupby, aggregations")

class DataQueryTool:
    def __init__(self):
        self.df = data_loader.load_data()
    
    def execute_query(self, execution_plan: str) -> str:
        """Execute data query based on execution plan"""
        try:
            plan = json.loads(execution_plan)
            result_df = self.df.copy()
            
            # Apply filters
            if 'filters' in plan and plan['filters']:
                for filter_condition in plan['filters']:
                    column = filter_condition['column']
                    operator = filter_condition['operator']
                    value = filter_condition['value']
                    
                    if operator == '==':
                        result_df = result_df[result_df[column] == value]
                    elif operator == '!=':
                        result_df = result_df[result_df[column] != value]
                    elif operator == '>':
                        result_df = result_df[result_df[column] > value]
                    elif operator == '<':
                        result_df = result_df[result_df[column] < value]
                    elif operator == '>=':
                        result_df = result_df[result_df[column] >= value]
                    elif operator == '<=':
                        result_df = result_df[result_df[column] <= value]
                    elif operator == 'in':
                        result_df = result_df[result_df[column].isin(value)]
            
            # Apply grouping and aggregations
            if 'groupby' in plan and plan['groupby']:
                agg_dict = {}
                for agg in plan.get('aggregations', []):
                    col = agg['column']
                    func = agg['function']
                    alias = agg.get('alias', f"{func}_{col}")
                    agg_dict[alias] = (col, func)
                
                result_df = result_df.groupby(plan['groupby']).agg(**agg_dict).reset_index()
            
            elif 'aggregations' in plan and plan['aggregations']:
                # Global aggregation without grouping
                result_dict = {}
                for agg in plan['aggregations']:
                    col = agg['column']
                    func = agg['function']
                    alias = agg.get('alias', f"{func}_{col}")
                    
                    if func == 'count':
                        result_dict[alias] = result_df[col].count()
                    elif func == 'sum':
                        result_dict[alias] = result_df[col].sum()
                    elif func == 'mean':
                        result_dict[alias] = result_df[col].mean()
                    elif func == 'median':
                        result_dict[alias] = result_df[col].median()
                    elif func == 'min':
                        result_dict[alias] = result_df[col].min()
                    elif func == 'max':
                        result_dict[alias] = result_df[col].max()
                
                result_df = pd.DataFrame([result_dict])
            
            # Apply sorting
            if 'sort' in plan and plan['sort']:
                sort_by = plan['sort']['by']
                ascending = plan['sort'].get('ascending', False)
                result_df = result_df.sort_values(by=sort_by, ascending=ascending)
            
            # Apply limit
            if 'limit' in plan and plan['limit']:
                result_df = result_df.head(plan['limit'])
            
            # Convert to dict for JSON serialization
            result = result_df.to_dict('records')
            
            return json.dumps({
                'success': True,
                'data': result,
                'row_count': len(result),
                'columns': list(result_df.columns) if len(result) > 0 else []
            }, default=str)
            
        except Exception as e:
            return json.dumps({
                'success': False,
                'error': str(e),
                'data': []
            })

def create_data_query_tool() :
    """Create the data query tool"""
    query_tool_instance = DataQueryTool()
    return StructuredTool.from_function(
        func=query_tool_instance.execute_query,
        name="query_transaction_data",
        description="Execute queries on transaction data based on execution plan. Input should be a JSON string with filters, groupby, aggregations, sort, and limit.",
        # func=query_tool_instance.execute_query,
        args_schema=QueryDataInput
    )