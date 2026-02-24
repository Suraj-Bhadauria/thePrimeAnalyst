"""
Time Analysis Tool for PayInsight AI

This module provides comprehensive temporal analysis capabilities for transaction data.
It handles all time-related queries including peak hours, hourly distributions,
day-of-week patterns, weekend vs weekday comparisons, time trends, and heatmap data.

Author: Team primeFactors
"""

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np
from scipy import stats
import json
from typing import Any, Dict, List, Optional, Tuple
from src.utils.data_loader import data_loader


class TimeAnalysisInput(BaseModel):
    """Input schema for time analysis tool."""
    
    analysis_type: str = Field(
        description="Type of time analysis: peak_hours, hourly_distribution, "
                    "day_of_week_pattern, weekend_vs_weekday, time_trend, "
                    "peak_hours_by_category, failure_heatmap_data, hourly_comparison"
    )
    parameters: str = Field(
        description="JSON string with optional parameters: filters (list), top_n (int), "
                    "metric (string), smoothing_window (int), segment_a/segment_b (dict), "
                    "include_stats (bool)"
    )


class TimeAnalysisTool:
    """
    Comprehensive time-based analysis tool for transaction data.
    
    This tool handles all temporal analysis including peak hours identification,
    hourly distributions, day-of-week patterns, weekend/weekday comparisons,
    time series trends, and failure heatmap generation.
    """
    
    # Period labels for hour classification
    PERIOD_LABELS: Dict[int, str] = {
        **{h: "Late Night" for h in range(0, 6)},
        **{h: "Morning" for h in range(6, 12)},
        **{h: "Afternoon" for h in range(12, 18)},
        **{h: "Evening Peak" for h in range(18, 22)},
        **{h: "Night" for h in range(22, 24)}
    }
    
    # Day name mapping
    DAY_NAMES: Dict[int, str] = {
        0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
        4: "Friday", 5: "Saturday", 6: "Sunday"
    }
    
    def __init__(self) -> None:
        """Initialize the TimeAnalysisTool with data from the singleton loader."""
        self.df = data_loader.load_data()
        self.total_records = len(self.df)
    
    def analyze(self, analysis_type: str, parameters: str) -> str:
        """
        Main entry point for time-based analysis.
        
        Args:
            analysis_type: The type of temporal analysis to perform.
            parameters: JSON string containing optional filters and configuration.
            
        Returns:
            JSON string with analysis results in standardized format.
        """
        try:
            params = json.loads(parameters) if parameters else {}
        except json.JSONDecodeError as e:
            return self._error_response(
                analysis_type,
                f"Invalid JSON in parameters: {str(e)}",
                "Ensure parameters is a valid JSON string"
            )
        
        # Route to appropriate analysis method
        analysis_methods = {
            'peak_hours': self._analyze_peak_hours,
            'hourly_distribution': self._analyze_hourly_distribution,
            'day_of_week_pattern': self._analyze_day_of_week_pattern,
            'weekend_vs_weekday': self._analyze_weekend_vs_weekday,
            'time_trend': self._analyze_time_trend,
            'peak_hours_by_category': self._analyze_peak_hours_by_category,
            'failure_heatmap_data': self._analyze_failure_heatmap,
            'hourly_comparison': self._analyze_hourly_comparison
        }
        
        if analysis_type not in analysis_methods:
            return self._error_response(
                analysis_type,
                f"Unknown analysis_type: {analysis_type}",
                f"Valid types: {', '.join(analysis_methods.keys())}"
            )
        
        try:
            return analysis_methods[analysis_type](params)
        except Exception as e:
            return self._error_response(
                analysis_type,
                f"Analysis failed: {str(e)}",
                "Check your filter parameters and try again"
            )
    
    def _apply_filters(self, df: pd.DataFrame, filters: List[Dict]) -> pd.DataFrame:
        """
        Apply filter conditions to DataFrame.
        
        Args:
            df: Input DataFrame to filter.
            filters: List of filter dictionaries with column, operator, value keys.
            
        Returns:
            Filtered DataFrame.
        """
        result_df = df.copy()
        
        for filter_cond in filters:
            column = data_loader.resolve_column(filter_cond.get('column', ''))
            operator = filter_cond.get('operator', '==')
            value = filter_cond.get('value')
            
            if column not in result_df.columns:
                continue
            
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
        
        return result_df
    
    def _build_hourly_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build comprehensive hourly statistics from transaction data.
        
        Args:
            df: DataFrame containing transaction data.
            
        Returns:
            DataFrame with hourly aggregated statistics.
        """
        if df.empty:
            return pd.DataFrame()
        
        # Aggregate by hour
        hourly = df.groupby('hour_of_day').agg(
            count=('transaction_id', 'count'),
            success_count=('transaction_status', lambda x: (x == 'SUCCESS').sum()),
            failed_count=('transaction_status', lambda x: (x == 'FAILED').sum()),
            pending_count=('transaction_status', lambda x: (x == 'PENDING').sum()),
            total_amount=('amount_inr', 'sum'),
            avg_amount=('amount_inr', 'mean'),
            fraud_count=('fraud_flag', 'sum')
        ).reset_index()
        
        # Calculate rates
        hourly['success_rate'] = np.round(
            hourly['success_count'] / hourly['count'] * 100, 2
        )
        hourly['failure_rate'] = np.round(
            hourly['failed_count'] / hourly['count'] * 100, 2
        )
        hourly['fraud_rate'] = np.round(
            hourly['fraud_count'] / hourly['count'] * 100, 2
        )
        hourly['avg_amount'] = np.round(hourly['avg_amount'], 2)
        hourly['total_amount'] = np.round(hourly['total_amount'], 2)
        
        # Add period labels and business hours flag
        hourly['period_label'] = hourly['hour_of_day'].map(self.PERIOD_LABELS)
        hourly['is_business_hours'] = hourly['hour_of_day'].between(9, 21)
        
        return hourly
    
    def _get_metric_column(self, metric: str) -> str:
        """
        Map metric name to DataFrame column name.
        
        Args:
            metric: Metric name from parameters.
            
        Returns:
            Corresponding DataFrame column name.
        """
        metric_map = {
            'volume': 'count',
            'failure_rate': 'failure_rate',
            'fraud_rate': 'fraud_rate',
            'avg_amount': 'avg_amount',
            'success_rate': 'success_rate',
            'total_amount': 'total_amount'
        }
        return metric_map.get(metric, 'count')
    
    def _format_hour_label(self, hour: int) -> str:
        """
        Format hour as human-readable string.
        
        Args:
            hour: Hour value (0-23).
            
        Returns:
            Formatted string like "7 PM (Hour 19)".
        """
        if hour == 0:
            return "12 AM (Hour 0)"
        elif hour < 12:
            return f"{hour} AM (Hour {hour})"
        elif hour == 12:
            return "12 PM (Hour 12)"
        else:
            return f"{hour - 12} PM (Hour {hour})"
    
    def _success_response(
        self,
        analysis_type: str,
        data: List[Dict],
        summary: Dict[str, Any],
        filters_applied: List[Dict],
        total_analyzed: int,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Build standardized success response.
        
        Args:
            analysis_type: Type of analysis performed.
            data: List of result records.
            summary: Summary dictionary with key findings.
            filters_applied: List of filters that were applied.
            total_analyzed: Number of records analyzed.
            metadata: Optional additional metadata.
            
        Returns:
            JSON string with standardized response format.
        """
        response = {
            "success": True,
            "analysis_type": analysis_type,
            "filters_applied": filters_applied,
            "total_records_analyzed": total_analyzed,
            "data": data,
            "summary": summary,
            "metadata": metadata or {
                "execution_note": "Analysis completed successfully",
                "data_coverage_pct": round(total_analyzed / self.total_records * 100, 2)
            }
        }
        return json.dumps(response, default=str)
    
    def _error_response(
        self,
        analysis_type: str,
        error: str,
        suggestion: str
    ) -> str:
        """
        Build standardized error response.
        
        Args:
            analysis_type: Type of analysis attempted.
            error: Error message.
            suggestion: Suggestion for resolution.
            
        Returns:
            JSON string with error response format.
        """
        return json.dumps({
            "success": False,
            "analysis_type": analysis_type,
            "error": error,
            "suggestion": suggestion
        })
    
    def _analyze_peak_hours(self, params: Dict) -> str:
        """
        Find the busiest hours of the day by transaction volume or other metrics.
        
        Args:
            params: Dictionary with optional filters, top_n, and metric.
            
        Returns:
            JSON string with peak hours analysis results.
        """
        filters = params.get('filters', [])
        top_n = params.get('top_n', 5)
        metric = params.get('metric', 'volume')
        
        # Apply filters
        df = self._apply_filters(self.df, filters)
        
        if df.empty:
            return self._error_response(
                'peak_hours',
                "No data remaining after applying filters",
                "Try broader filter criteria"
            )
        
        # Build hourly stats
        hourly = self._build_hourly_stats(df)
        
        # Sort by metric
        metric_col = self._get_metric_column(metric)
        hourly_sorted = hourly.sort_values(metric_col, ascending=False)
        
        # Get top N
        top_hours = hourly_sorted.head(top_n)
        
        # Build response data
        data = top_hours.to_dict('records')
        
        # Find peak and lowest
        peak_hour = int(hourly_sorted.iloc[0]['hour_of_day'])
        lowest_hour = int(hourly_sorted.iloc[-1]['hour_of_day'])
        peak_value = hourly_sorted.iloc[0][metric_col]
        
        # Build key finding
        if metric == 'volume':
            key_finding = (
                f"{self._format_hour_label(peak_hour)} is the peak with "
                f"{int(peak_value):,} transactions and a "
                f"{hourly_sorted.iloc[0]['failure_rate']:.2f}% failure rate"
            )
        else:
            key_finding = (
                f"{self._format_hour_label(peak_hour)} has the highest {metric} "
                f"at {peak_value:.2f}"
            )
        
        summary = {
            "key_finding": key_finding,
            "peak_period": self._format_hour_label(peak_hour),
            "lowest_period": self._format_hour_label(lowest_hour),
            "metric_used": metric
        }
        
        metadata = {
            "execution_note": f"Returned top {top_n} hours by {metric}",
            "data_coverage_pct": round(len(df) / self.total_records * 100, 2)
        }
        
        return self._success_response(
            'peak_hours', data, summary, filters, len(df), metadata
        )
    
    def _analyze_hourly_distribution(self, params: Dict) -> str:
        """
        Generate complete 24-hour breakdown of transaction metrics.
        
        Args:
            params: Dictionary with optional filters and metric.
            
        Returns:
            JSON string with full hourly distribution.
        """
        filters = params.get('filters', [])
        
        # Apply filters
        df = self._apply_filters(self.df, filters)
        
        if df.empty:
            return self._error_response(
                'hourly_distribution',
                "No data remaining after applying filters",
                "Try broader filter criteria"
            )
        
        # Build hourly stats
        hourly = self._build_hourly_stats(df)
        
        # Ensure all 24 hours are present
        all_hours = pd.DataFrame({'hour_of_day': range(24)})
        hourly = all_hours.merge(hourly, on='hour_of_day', how='left').fillna(0)
        
        # Recalculate labels for filled hours
        hourly['period_label'] = hourly['hour_of_day'].map(self.PERIOD_LABELS)
        hourly['is_business_hours'] = hourly['hour_of_day'].between(9, 21)
        
        # Sort by hour
        hourly = hourly.sort_values('hour_of_day')
        
        # Add cumulative volume percentage
        total_count = hourly['count'].sum()
        if total_count > 0:
            hourly['cumulative_volume_pct'] = np.round(
                hourly['count'].cumsum() / total_count * 100, 2
            )
        else:
            hourly['cumulative_volume_pct'] = 0.0
        
        data = hourly.to_dict('records')
        
        # Find peak and lowest (excluding zero-count hours)
        non_zero = hourly[hourly['count'] > 0]
        if not non_zero.empty:
            peak_idx = non_zero['count'].idxmax()
            lowest_idx = non_zero['count'].idxmin()
            peak_hour = int(hourly.loc[peak_idx, 'hour_of_day'])
            lowest_hour = int(hourly.loc[lowest_idx, 'hour_of_day'])
            peak_count = int(hourly.loc[peak_idx, 'count'])
        else:
            peak_hour, lowest_hour, peak_count = 0, 0, 0
        
        summary = {
            "key_finding": (
                f"Transaction volume peaks at {self._format_hour_label(peak_hour)} "
                f"with {peak_count:,} transactions; lowest at {self._format_hour_label(lowest_hour)}"
            ),
            "peak_period": self._format_hour_label(peak_hour),
            "lowest_period": self._format_hour_label(lowest_hour),
            "metric_used": "volume"
        }
        
        return self._success_response(
            'hourly_distribution', data, summary, filters, len(df)
        )
    
    def _analyze_day_of_week_pattern(self, params: Dict) -> str:
        """
        Analyze transaction patterns across days of the week.
        
        Args:
            params: Dictionary with optional filters.
            
        Returns:
            JSON string with day-of-week pattern analysis.
        """
        filters = params.get('filters', [])
        
        # Apply filters
        df = self._apply_filters(self.df, filters)
        
        if df.empty:
            return self._error_response(
                'day_of_week_pattern',
                "No data remaining after applying filters",
                "Try broader filter criteria"
            )
        
        # Aggregate by day of week
        daily = df.groupby('day_of_week').agg(
            count=('transaction_id', 'count'),
            success_count=('transaction_status', lambda x: (x == 'SUCCESS').sum()),
            failed_count=('transaction_status', lambda x: (x == 'FAILED').sum()),
            total_amount=('amount_inr', 'sum'),
            avg_amount=('amount_inr', 'mean'),
            fraud_count=('fraud_flag', 'sum')
        ).reset_index()
        
        # Calculate rates
        daily['success_rate'] = np.round(daily['success_count'] / daily['count'] * 100, 2)
        daily['failure_rate'] = np.round(daily['failed_count'] / daily['count'] * 100, 2)
        daily['fraud_rate'] = np.round(daily['fraud_count'] / daily['count'] * 100, 2)
        daily['avg_amount'] = np.round(daily['avg_amount'], 2)
        daily['total_amount'] = np.round(daily['total_amount'], 2)
        
        # Add day name and weekend flag
        daily['day_name'] = daily['day_of_week'].map(self.DAY_NAMES)
        daily['is_weekend'] = daily['day_of_week'].isin([5, 6])
        
        # Calculate vs weekly average
        weekly_avg = daily['count'].mean()
        daily['vs_weekly_avg'] = np.round(
            (daily['count'] - weekly_avg) / weekly_avg * 100, 2
        )
        
        # Sort by day of week (Monday first)
        daily = daily.sort_values('day_of_week')
        
        data = daily.to_dict('records')
        
        # Find busiest and slowest days
        peak_idx = daily['count'].idxmax()
        lowest_idx = daily['count'].idxmin()
        peak_day = daily.loc[peak_idx, 'day_name']
        lowest_day = daily.loc[lowest_idx, 'day_name']
        peak_count = int(daily.loc[peak_idx, 'count'])
        
        summary = {
            "key_finding": (
                f"{peak_day} is the busiest day with {peak_count:,} transactions, "
                f"while {lowest_day} has the lowest volume"
            ),
            "peak_period": peak_day,
            "lowest_period": lowest_day,
            "metric_used": "volume"
        }
        
        return self._success_response(
            'day_of_week_pattern', data, summary, filters, len(df)
        )
    
    def _analyze_weekend_vs_weekday(self, params: Dict) -> str:
        """
        Compare weekend and weekday transaction patterns with statistical validation.
        
        Args:
            params: Dictionary with optional filters.
            
        Returns:
            JSON string with weekend vs weekday comparison including Chi-Square test.
        """
        filters = params.get('filters', [])
        
        # Apply filters
        df = self._apply_filters(self.df, filters)
        
        if df.empty:
            return self._error_response(
                'weekend_vs_weekday',
                "No data remaining after applying filters",
                "Try broader filter criteria"
            )
        
        # Split by weekend
        weekday_df = df[~df['is_weekend']]
        weekend_df = df[df['is_weekend']]
        
        def compute_segment_stats(segment_df: pd.DataFrame, label: str) -> Dict:
            """Compute statistics for a segment."""
            if segment_df.empty:
                return {
                    "segment": label,
                    "total_transactions": 0,
                    "success_count": 0,
                    "failed_count": 0,
                    "success_rate": 0.0,
                    "failure_rate": 0.0,
                    "avg_amount": 0.0,
                    "total_amount": 0.0,
                    "fraud_rate": 0.0,
                    "avg_hour_of_day": 0.0
                }
            
            total = len(segment_df)
            success = (segment_df['transaction_status'] == 'SUCCESS').sum()
            failed = (segment_df['transaction_status'] == 'FAILED').sum()
            
            return {
                "segment": label,
                "total_transactions": int(total),
                "success_count": int(success),
                "failed_count": int(failed),
                "success_rate": round(success / total * 100, 2),
                "failure_rate": round(failed / total * 100, 2),
                "avg_amount": round(segment_df['amount_inr'].mean(), 2),
                "total_amount": round(segment_df['amount_inr'].sum(), 2),
                "fraud_rate": round(segment_df['fraud_flag'].sum() / total * 100, 2),
                "avg_hour_of_day": round(segment_df['hour_of_day'].mean(), 2)
            }
        
        weekday_stats = compute_segment_stats(weekday_df, "weekday")
        weekend_stats = compute_segment_stats(weekend_df, "weekend")
        
        # Calculate differences
        differences = {}
        for key in ['failure_rate', 'success_rate', 'avg_amount', 'fraud_rate']:
            weekday_val = weekday_stats[key]
            weekend_val = weekend_stats[key]
            abs_diff = round(weekend_val - weekday_val, 2)
            pct_diff = round(abs_diff / weekday_val * 100, 2) if weekday_val != 0 else 0.0
            differences[key] = {
                "absolute_difference": abs_diff,
                "percentage_difference": pct_diff,
                "direction": "higher on weekends" if abs_diff > 0 else "lower on weekends"
            }
        
        # Chi-Square test for statistical significance
        # Build contingency table: [weekday/weekend] × [SUCCESS/FAILED]
        weekday_success = weekday_stats['success_count']
        weekday_failed = weekday_stats['failed_count']
        weekend_success = weekend_stats['success_count']
        weekend_failed = weekend_stats['failed_count']
        
        contingency_table = np.array([
            [weekday_success, weekday_failed],
            [weekend_success, weekend_failed]
        ])
        
        # Perform Chi-Square test if we have valid data
        if contingency_table.min() >= 0 and contingency_table.sum() > 0:
            chi2, p_value, dof, expected = stats.chi2_contingency(contingency_table)
            significance_statement = (
                "Statistically significant difference" if p_value < 0.05 
                else "No statistically significant difference"
            )
            chi_square_result = {
                "chi2_statistic": round(chi2, 4),
                "p_value": round(p_value, 6),
                "degrees_of_freedom": int(dof),
                "significant": p_value < 0.05,
                "significance_statement": significance_statement
            }
        else:
            chi_square_result = {
                "chi2_statistic": None,
                "p_value": None,
                "significant": False,
                "significance_statement": "Insufficient data for statistical test"
            }
        
        data = [
            weekday_stats,
            weekend_stats,
            {"differences": differences},
            {"statistical_test": chi_square_result}
        ]
        
        # Key finding
        failure_diff = differences['failure_rate']['absolute_difference']
        direction = "higher" if failure_diff > 0 else "lower"
        
        summary = {
            "key_finding": (
                f"Weekend failure rate ({weekend_stats['failure_rate']}%) is "
                f"{abs(failure_diff):.2f}% {direction} than weekday ({weekday_stats['failure_rate']}%). "
                f"{chi_square_result['significance_statement']}"
            ),
            "peak_period": "weekday" if weekday_stats['total_transactions'] > weekend_stats['total_transactions'] else "weekend",
            "lowest_period": "weekend" if weekday_stats['total_transactions'] > weekend_stats['total_transactions'] else "weekday",
            "metric_used": "failure_rate"
        }
        
        return self._success_response(
            'weekend_vs_weekday', data, summary, filters, len(df)
        )
    
    def _analyze_time_trend(self, params: Dict) -> str:
        """
        Generate time trend with rolling average smoothing.
        
        Args:
            params: Dictionary with optional filters, metric, and smoothing_window.
            
        Returns:
            JSON string with time trend analysis.
        """
        filters = params.get('filters', [])
        metric = params.get('metric', 'volume')
        smoothing_window = params.get('smoothing_window', 3)
        
        # Apply filters
        df = self._apply_filters(self.df, filters)
        
        if df.empty:
            return self._error_response(
                'time_trend',
                "No data remaining after applying filters",
                "Try broader filter criteria"
            )
        
        # Build hourly stats
        hourly = self._build_hourly_stats(df)
        
        # Ensure all 24 hours present
        all_hours = pd.DataFrame({'hour_of_day': range(24)})
        hourly = all_hours.merge(hourly, on='hour_of_day', how='left').fillna(0)
        hourly = hourly.sort_values('hour_of_day')
        
        # Get metric column
        metric_col = self._get_metric_column(metric)
        
        # Apply rolling SMA
        hourly['raw_value'] = hourly[metric_col]
        hourly['sma_value'] = hourly[metric_col].rolling(
            window=smoothing_window, min_periods=1, center=True
        ).mean().round(2)
        
        # Calculate trend direction
        first_half_avg = hourly[hourly['hour_of_day'] < 12][metric_col].mean()
        second_half_avg = hourly[hourly['hour_of_day'] >= 12][metric_col].mean()
        
        if first_half_avg == 0:
            trend_direction = "Stable"
        else:
            change_pct = (second_half_avg - first_half_avg) / first_half_avg * 100
            if change_pct > 5:
                trend_direction = "Rising"
            elif change_pct < -5:
                trend_direction = "Falling"
            else:
                trend_direction = "Stable"
        
        # Add trend info to each record
        hourly['trend_direction'] = trend_direction
        
        data = hourly[['hour_of_day', 'raw_value', 'sma_value', 'period_label', 'trend_direction']].to_dict('records')
        
        # Find peak
        peak_idx = hourly['raw_value'].idxmax()
        peak_hour = int(hourly.loc[peak_idx, 'hour_of_day'])
        lowest_idx = hourly['raw_value'].idxmin()
        lowest_hour = int(hourly.loc[lowest_idx, 'hour_of_day'])
        
        summary = {
            "key_finding": (
                f"Transaction {metric} shows a {trend_direction.lower()} trend "
                f"throughout the day, peaking at {self._format_hour_label(peak_hour)}"
            ),
            "peak_period": self._format_hour_label(peak_hour),
            "lowest_period": self._format_hour_label(lowest_hour),
            "metric_used": metric
        }
        
        metadata = {
            "execution_note": f"Applied {smoothing_window}-hour rolling SMA smoothing",
            "data_coverage_pct": round(len(df) / self.total_records * 100, 2)
        }
        
        return self._success_response(
            'time_trend', data, summary, filters, len(df), metadata
        )
    
    def _analyze_peak_hours_by_category(self, params: Dict) -> str:
        """
        Find peak hours filtered by merchant category or transaction type.
        
        Args:
            params: Dictionary with required filters, optional top_n and metric.
            
        Returns:
            JSON string with category-filtered peak hours.
        """
        filters = params.get('filters', [])
        top_n = params.get('top_n', 5)
        metric = params.get('metric', 'volume')
        
        if not filters:
            return self._error_response(
                'peak_hours_by_category',
                "No filters provided - this analysis requires category/type filters",
                "Add filters like {'column': 'merchant_category', 'operator': '==', 'value': 'Food'}"
            )
        
        # Apply filters
        df = self._apply_filters(self.df, filters)
        
        if df.empty:
            return self._error_response(
                'peak_hours_by_category',
                "No data remaining after applying filters",
                "Try broader filter criteria or check filter values"
            )
        
        # Build hourly stats
        hourly = self._build_hourly_stats(df)
        
        # Sort by metric
        metric_col = self._get_metric_column(metric)
        hourly_sorted = hourly.sort_values(metric_col, ascending=False)
        
        # Get top N
        top_hours = hourly_sorted.head(top_n)
        
        # Calculate category context
        category_pct = round(len(df) / self.total_records * 100, 2)
        filter_desc = ", ".join([f"{f['column']}={f['value']}" for f in filters])
        
        # Add category context to each record
        top_hours = top_hours.copy()
        top_hours['category_context'] = f"Filtered by: {filter_desc} ({category_pct}% of total)"
        
        data = top_hours.to_dict('records')
        
        # Find peak
        peak_hour = int(hourly_sorted.iloc[0]['hour_of_day'])
        lowest_hour = int(hourly_sorted.iloc[-1]['hour_of_day'])
        peak_value = hourly_sorted.iloc[0][metric_col]
        
        if metric == 'volume':
            key_finding = (
                f"For {filter_desc}: {self._format_hour_label(peak_hour)} is the peak "
                f"with {int(peak_value):,} transactions ({category_pct}% of all data)"
            )
        else:
            key_finding = (
                f"For {filter_desc}: {self._format_hour_label(peak_hour)} has the highest {metric} "
                f"at {peak_value:.2f}"
            )
        
        summary = {
            "key_finding": key_finding,
            "peak_period": self._format_hour_label(peak_hour),
            "lowest_period": self._format_hour_label(lowest_hour),
            "metric_used": metric
        }
        
        metadata = {
            "execution_note": f"Filter: {filter_desc} reduced dataset to {len(df):,} rows",
            "data_coverage_pct": category_pct
        }
        
        return self._success_response(
            'peak_hours_by_category', data, summary, filters, len(df), metadata
        )
    
    def _analyze_failure_heatmap(self, params: Dict) -> str:
        """
        Generate hour × day_of_week failure rate matrix for heatmap visualization.
        
        Args:
            params: Dictionary with optional filters.
            
        Returns:
            JSON string with heatmap data structure.
        """
        filters = params.get('filters', [])
        
        # Apply filters
        df = self._apply_filters(self.df, filters)
        
        if df.empty:
            return self._error_response(
                'failure_heatmap_data',
                "No data remaining after applying filters",
                "Try broader filter criteria"
            )
        
        # Build pivot table: hour × day failure rate
        df_copy = df.copy()
        df_copy['is_failed'] = (df_copy['transaction_status'] == 'FAILED').astype(int)
        
        pivot = df_copy.pivot_table(
            values='is_failed',
            index='hour_of_day',
            columns='day_of_week',
            aggfunc='mean'
        ) * 100  # Convert to percentage
        
        # Fill missing combinations with 0
        pivot = pivot.reindex(
            index=range(24),
            columns=range(7),
            fill_value=0
        )
        
        pivot = pivot.round(2)
        
        # Calculate row and column averages
        row_avg = pivot.mean(axis=1).round(2)
        col_avg = pivot.mean(axis=0).round(2)
        
        # Find hotspot (worst cell)
        max_val = pivot.max().max()
        hotspot_coords = np.where(pivot.values == max_val)
        hotspot_hour = int(hotspot_coords[0][0])
        hotspot_day = int(hotspot_coords[1][0])
        
        # Build heatmap data as list of records
        heatmap_data = []
        for hour in range(24):
            for day in range(7):
                heatmap_data.append({
                    "hour_of_day": hour,
                    "day_of_week": day,
                    "day_name": self.DAY_NAMES[day],
                    "failure_rate": float(pivot.loc[hour, day]),
                    "is_hotspot": (hour == hotspot_hour and day == hotspot_day)
                })
        
        # Add averages as separate structure
        averages = {
            "row_averages": {h: float(row_avg[h]) for h in range(24)},
            "column_averages": {d: float(col_avg[d]) for d in range(7)}
        }
        
        data = heatmap_data
        
        summary = {
            "key_finding": (
                f"Highest failure rate ({max_val:.2f}%) occurs at "
                f"{self._format_hour_label(hotspot_hour)} on {self.DAY_NAMES[hotspot_day]}"
            ),
            "peak_period": f"{self._format_hour_label(hotspot_hour)} on {self.DAY_NAMES[hotspot_day]}",
            "lowest_period": "varies",
            "metric_used": "failure_rate"
        }
        
        metadata = {
            "execution_note": "Generated 24x7 heatmap matrix",
            "data_coverage_pct": round(len(df) / self.total_records * 100, 2),
            "averages": averages,
            "hotspot": {
                "hour": hotspot_hour,
                "day": hotspot_day,
                "day_name": self.DAY_NAMES[hotspot_day],
                "failure_rate": float(max_val)
            }
        }
        
        return self._success_response(
            'failure_heatmap_data', data, summary, filters, len(df), metadata
        )
    
    def _analyze_hourly_comparison(self, params: Dict) -> str:
        """
        Compare two segments (e.g., Android vs iOS) across hours.
        
        Args:
            params: Dictionary with segment_a, segment_b definitions,
                    optional filters and include_stats flag.
            
        Returns:
            JSON string with hourly comparison between segments.
        """
        filters = params.get('filters', [])
        segment_a = params.get('segment_a', {})
        segment_b = params.get('segment_b', {})
        include_stats = params.get('include_stats', False)
        
        if not segment_a or not segment_b:
            return self._error_response(
                'hourly_comparison',
                "Missing segment_a or segment_b parameters",
                "Provide segment definitions like {'column': 'device_type', 'value': 'Android'}"
            )
        
        # Apply base filters first
        df = self._apply_filters(self.df, filters)
        
        if df.empty:
            return self._error_response(
                'hourly_comparison',
                "No data remaining after applying filters",
                "Try broader filter criteria"
            )
        
        # Split into segments
        col_a = segment_a.get('column')
        val_a = segment_a.get('value')
        col_b = segment_b.get('column')
        val_b = segment_b.get('value')
        
        df_a = df[df[col_a] == val_a] if col_a in df.columns else pd.DataFrame()
        df_b = df[df[col_b] == val_b] if col_b in df.columns else pd.DataFrame()
        
        if df_a.empty or df_b.empty:
            return self._error_response(
                'hourly_comparison',
                f"One or both segments have no data (A: {len(df_a)}, B: {len(df_b)})",
                "Check segment column and value specifications"
            )
        
        # Build hourly stats for each segment
        hourly_a = self._build_hourly_stats(df_a)
        hourly_b = self._build_hourly_stats(df_b)
        
        # Ensure all 24 hours
        all_hours = pd.DataFrame({'hour_of_day': range(24)})
        hourly_a = all_hours.merge(hourly_a, on='hour_of_day', how='left').fillna(0)
        hourly_b = all_hours.merge(hourly_b, on='hour_of_day', how='left').fillna(0)
        
        hourly_a = hourly_a.sort_values('hour_of_day')
        hourly_b = hourly_b.sort_values('hour_of_day')
        
        # Build comparison data
        comparison_data = []
        max_delta = 0
        peak_divergence_hour = 0
        
        for hour in range(24):
            row_a = hourly_a[hourly_a['hour_of_day'] == hour].iloc[0]
            row_b = hourly_b[hourly_b['hour_of_day'] == hour].iloc[0]
            
            count_delta = float(row_a['count'] - row_b['count'])
            failure_delta = float(row_a['failure_rate'] - row_b['failure_rate'])
            success_delta = float(row_a['success_rate'] - row_b['success_rate'])
            
            # Track max divergence
            if abs(count_delta) > abs(max_delta):
                max_delta = count_delta
                peak_divergence_hour = hour
            
            comparison_data.append({
                "hour_of_day": hour,
                "period_label": self.PERIOD_LABELS[hour],
                f"segment_a_{val_a}_count": int(row_a['count']),
                f"segment_a_{val_a}_failure_rate": round(float(row_a['failure_rate']), 2),
                f"segment_a_{val_a}_success_rate": round(float(row_a['success_rate']), 2),
                f"segment_b_{val_b}_count": int(row_b['count']),
                f"segment_b_{val_b}_failure_rate": round(float(row_b['failure_rate']), 2),
                f"segment_b_{val_b}_success_rate": round(float(row_b['success_rate']), 2),
                "count_delta": round(count_delta, 2),
                "failure_rate_delta": round(failure_delta, 2),
                "success_rate_delta": round(success_delta, 2)
            })
        
        # Statistical test if requested
        stat_result = None
        if include_stats:
            amounts_a = df_a['amount_inr'].dropna().values
            amounts_b = df_b['amount_inr'].dropna().values
            
            if len(amounts_a) > 1 and len(amounts_b) > 1:
                t_stat, p_value = stats.ttest_ind(amounts_a, amounts_b)
                stat_result = {
                    "test_type": "Independent T-Test (amount distributions)",
                    "t_statistic": round(float(t_stat), 4),
                    "p_value": round(float(p_value), 6),
                    "significant": p_value < 0.05,
                    "interpretation": (
                        f"Significant difference in transaction amounts between {val_a} and {val_b}"
                        if p_value < 0.05 else
                        f"No significant difference in transaction amounts between {val_a} and {val_b}"
                    )
                }
        
        data = comparison_data
        if stat_result:
            data.append({"statistical_test": stat_result})
        
        # Add divergence info
        data.append({
            "peak_divergence": {
                "hour": peak_divergence_hour,
                "hour_label": self._format_hour_label(peak_divergence_hour),
                "max_count_delta": round(max_delta, 2)
            }
        })
        
        # Key finding
        dominant_segment = val_a if max_delta > 0 else val_b
        
        summary = {
            "key_finding": (
                f"{val_a} vs {val_b}: Maximum divergence at {self._format_hour_label(peak_divergence_hour)} "
                f"where {dominant_segment} leads by {abs(int(max_delta)):,} transactions"
            ),
            "peak_period": self._format_hour_label(peak_divergence_hour),
            "lowest_period": "varies",
            "metric_used": "volume_comparison"
        }
        
        metadata = {
            "execution_note": f"Compared {val_a} ({len(df_a):,} rows) vs {val_b} ({len(df_b):,} rows)",
            "data_coverage_pct": round((len(df_a) + len(df_b)) / self.total_records * 100, 2)
        }
        
        return self._success_response(
            'hourly_comparison', data, summary, filters, len(df_a) + len(df_b), metadata
        )


def create_time_analysis_tool() -> StructuredTool:
    """
    Factory function to create the time analysis tool for LangChain.
    
    Returns:
        StructuredTool configured for time-based analysis.
    """
    tool_instance = TimeAnalysisTool()
    
    return StructuredTool.from_function(
        func=tool_instance.analyze,
        name="time_analysis_tool",
        description=(
            "For ALL time-based and temporal analysis of transaction data. "
            "Use this for questions about peak hours, hourly patterns, day-of-week trends, "
            "weekend vs weekday comparisons, time-series trends, and heatmap data. "
            "Supports filters on any column including receiver_bank, receiver_age_group, "
            "merchant_category, day_of_week, is_weekend. "
            "Input: analysis_type (string: peak_hours, hourly_distribution, day_of_week_pattern, "
            "weekend_vs_weekday, time_trend, peak_hours_by_category, failure_heatmap_data, "
            "hourly_comparison) and parameters (JSON string with optional filters, metric, "
            "top_n, smoothing_window, segment_a/segment_b, include_stats)."
        ),
        args_schema=TimeAnalysisInput
    )
