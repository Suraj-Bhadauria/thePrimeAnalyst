from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np
from scipy import stats
import json
from src.utils.data_loader import data_loader

class StatsAnalysisInput(BaseModel):
    analysis_type: str = Field(description="Type of analysis: failure_rate, fraud_rate, correlation, trend, distribution")
    parameters: str = Field(description="JSON string with parameters for the analysis")

class StatisticalTools:
    def __init__(self):
        self.df = data_loader.load_data()
    
    def analyze(self, analysis_type: str, parameters: str) -> str:
        """Perform statistical analysis"""
        try:
            params = json.loads(parameters)
            
            if analysis_type == 'failure_rate':
                return self._calculate_failure_rate(params)
            elif analysis_type == 'fraud_rate':
                return self._calculate_fraud_rate(params)
            elif analysis_type == 'correlation':
                return self._analyze_correlation(params)
            elif analysis_type == 'distribution':
                return self._analyze_distribution(params)
            elif analysis_type == 'comparison':
                return self._compare_segments(params)
            else:
                return json.dumps({'success': False, 'error': 'Unknown analysis type'})
                
        except Exception as e:
            return json.dumps({'success': False, 'error': str(e)})
    
    def _calculate_failure_rate(self, params: dict) -> str:
        """Calculate failure rate by segment"""
        df = self.df.copy()
        
        # Apply filters
        if 'filters' in params:
            for filter_cond in params['filters']:
                col = filter_cond['column']
                val = filter_cond['value']
                df = df[df[col] == val]
        
        # Calculate by segment
        segment = params.get('segment_by')
        
        if segment:
            results = df.groupby(segment).apply(
                lambda x: {
                    'total': len(x),
                    'failed': (x['transaction_status'] == 'FAILED').sum(),
                    'failure_rate': (x['transaction_status'] == 'FAILED').sum() / len(x) * 100 if len(x) > 0 else 0
                }
            ).to_dict()
        else:
            total = len(df)
            failed = (df['transaction_status'] == 'FAILED').sum()
            results = {
                'overall': {
                    'total': total,
                    'failed': failed,
                    'failure_rate': failed / total * 100 if total > 0 else 0
                }
            }
        
        return json.dumps({'success': True, 'analysis': 'failure_rate', 'results': results}, default=str)
    
    def _calculate_fraud_rate(self, params: dict) -> str:
        """Calculate fraud flag rate"""
        df = self.df.copy()
        
        if 'filters' in params:
            for filter_cond in params['filters']:
                col = filter_cond['column']
                val = filter_cond['value']
                df = df[df[col] == val]
        
        segment = params.get('segment_by')
        
        if segment:
            results = df.groupby(segment).apply(
                lambda x: {
                    'total': len(x),
                    'flagged': x['fraud_flag'].sum() if 'fraud_flag' in x.columns else 0,
                    'fraud_rate': x['fraud_flag'].sum() / len(x) * 100 if len(x) > 0 and 'fraud_flag' in x.columns else 0
                }
            ).to_dict()
        else:
            total = len(df)
            flagged = df['fraud_flag'].sum() if 'fraud_flag' in df.columns else 0
            results = {
                'overall': {
                    'total': total,
                    'flagged': flagged,
                    'fraud_rate': flagged / total * 100 if total > 0 else 0
                }
            }
        
        return json.dumps({'success': True, 'analysis': 'fraud_rate', 'results': results}, default=str)
    
    def _analyze_correlation(self, params: dict) -> str:
        """Analyze correlation between two categorical variables"""
        var1 = params['variable1']
        var2 = params['variable2']
        
        contingency_table = pd.crosstab(self.df[var1], self.df[var2])
        chi2, p_value, dof, expected = stats.chi2_contingency(contingency_table)
        
        results = {
            'chi2_statistic': chi2,
            'p_value': p_value,
            'degrees_of_freedom': dof,
            'significant': p_value < 0.05,
            'interpretation': 'Significant relationship exists' if p_value < 0.05 else 'No significant relationship'
        }
        
        return json.dumps({'success': True, 'analysis': 'correlation', 'results': results}, default=str)
    
    def _analyze_distribution(self, params: dict) -> str:
        """Analyze distribution of a metric"""
        column = params['column']
        data = self.df[column].dropna()
        
        results = {
            'mean': float(data.mean()),
            'median': float(data.median()),
            'std': float(data.std()),
            'min': float(data.min()),
            'max': float(data.max()),
            'q25': float(data.quantile(0.25)),
            'q75': float(data.quantile(0.75))
        }
        
        return json.dumps({'success': True, 'analysis': 'distribution', 'results': results}, default=str)
    
    def _compare_segments(self, params: dict) -> str:
        """Compare metrics across segments"""
        segment_col = params['segment_by']
        metric_col = params['metric']
        
        results = self.df.groupby(segment_col)[metric_col].agg(['count', 'mean', 'median', 'sum']).to_dict('index')
        
        return json.dumps({'success': True, 'analysis': 'comparison', 'results': results}, default=str)

def create_stats_tool():
    """Create statistical analysis tool"""
    stats_tool_instance = StatisticalTools()
    return StructuredTool.from_function(
        func=stats_tool_instance.analyze,
        name="statistical_analysis",
        description="Perform statistical analysis like failure_rate, fraud_rate, correlation, distribution, comparison. Input: analysis_type and parameters as JSON string.",
        # func=stats_tool_instance.analyze,
        args_schema=StatsAnalysisInput
    )