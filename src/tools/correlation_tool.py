"""
Correlation & Feature Importance Tool for PayInsight AI

This module provides comprehensive correlation analysis, feature importance
ranking, Cramér's V association matrices, interaction effect detection,
multivariate combination analysis, and point-biserial correlation between
continuous and binary variables.

Author: Team primeFactors
"""

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np
from scipy import stats
import json
import math
from typing import Any, Dict, List, Optional, Tuple
from src.utils.data_loader import data_loader


# ---------------------------------------------------------------------------
# Input schema
# ---------------------------------------------------------------------------

class CorrelationInput(BaseModel):
    """Input schema for correlation tool."""

    analysis_type: str = Field(
        description=(
            "Type of correlation analysis: feature_importance, cramers_v_matrix, "
            "interaction_effects, multivariate_combination, point_biserial"
        )
    )
    parameters: str = Field(
        description=(
            "JSON string with analysis parameters: target (failure/fraud/success), "
            "filters (list), factor_a (column), factor_b (column), factors (list of columns), "
            "top_n (int), min_sample_size (int), include_geography (bool), "
            "continuous_var (column), binary_target (string), include_distribution (bool), "
            "segment_by (column)"
        )
    )


# ---------------------------------------------------------------------------
# Main tool class
# ---------------------------------------------------------------------------

class CorrelationTool:
    """
    Comprehensive correlation and feature importance tool for transaction data.

    Handles feature importance ranking (Cramér's V per factor), full pairwise
    association matrix, two-factor interaction effects, multivariate combination
    risk profiling, and point-biserial correlation between amount and binary
    outcomes — each with statistical significance testing and plain-language
    interpretation.
    """

    def __init__(self) -> None:
        """Initialize CorrelationTool with data from the singleton loader."""
        self.df: pd.DataFrame = data_loader.load_data()
        self.total_records: int = len(self.df)

    # ------------------------------------------------------------------
    # Numpy-safe JSON serializer
    # ------------------------------------------------------------------

    class _NumpyEncoder(json.JSONEncoder):
        """JSON encoder that converts numpy types to native Python types."""
        def default(self, obj):
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, (np.bool_,)):
                return bool(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return super().default(obj)

    def _to_json(self, data: dict) -> str:
        """Serialize dict to JSON, handling numpy types."""
        return json.dumps(data, cls=self._NumpyEncoder)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def analyze(self, analysis_type: str, parameters: str) -> str:
        """
        Main entry point for correlation and feature importance analysis.

        Args:
            analysis_type: The type of analysis to perform.
            parameters: JSON string containing analysis parameters.

        Returns:
            JSON string with analysis results in standardised format.
        """
        try:
            params: Dict = json.loads(parameters) if parameters else {}
        except json.JSONDecodeError as exc:
            return self._error_response(
                analysis_type,
                f"Invalid JSON in parameters: {exc}",
                "Ensure parameters is a valid JSON string",
            )

        dispatch = {
            "feature_importance": self._feature_importance,
            "cramers_v_matrix": self._cramers_v_matrix,
            "interaction_effects": self._interaction_effects,
            "multivariate_combination": self._multivariate_combination,
            "point_biserial": self._point_biserial,
        }

        if analysis_type not in dispatch:
            return self._error_response(
                analysis_type,
                f"Unknown analysis_type: {analysis_type}",
                f"Valid types: {', '.join(dispatch.keys())}",
            )

        try:
            return dispatch[analysis_type](params)
        except Exception as exc:
            return self._error_response(
                analysis_type,
                f"Analysis failed: {exc}",
                "Check parameters and try again",
            )

    # ------------------------------------------------------------------
    # Helper: apply filters
    # ------------------------------------------------------------------

    def _apply_filters(self, df: pd.DataFrame, filters: List[Dict]) -> pd.DataFrame:
        """Apply a list of filter conditions to the DataFrame."""
        for f in filters:
            col = f.get("column", "")
            col = data_loader.resolve_column(col)
            op = f.get("operator", "==")
            val = f.get("value")
            if col not in df.columns:
                continue
            if op == "==":
                df = df[df[col] == val]
            elif op == "!=":
                df = df[df[col] != val]
            elif op == ">":
                df = df[df[col] > float(val)]
            elif op == "<":
                df = df[df[col] < float(val)]
            elif op == ">=":
                df = df[df[col] >= float(val)]
            elif op == "<=":
                df = df[df[col] <= float(val)]
            elif op == "in":
                if isinstance(val, list):
                    df = df[df[col].isin(val)]
        return df

    # ------------------------------------------------------------------
    # Helper: create binary target column
    # ------------------------------------------------------------------

    def _create_binary_target(self, df: pd.DataFrame, target: str) -> Tuple[pd.DataFrame, str]:
        """Create a binary target column based on the target parameter.

        Returns:
            Tuple of (dataframe with new column, column name).
        """
        if target == "failure":
            df = df.copy()
            df["_target"] = (df["transaction_status"] == "FAILED").astype(int)
            return df, "_target"
        elif target == "fraud":
            df = df.copy()
            df["_target"] = df["fraud_flag"].astype(int)
            return df, "_target"
        elif target == "success":
            df = df.copy()
            df["_target"] = (df["transaction_status"] == "SUCCESS").astype(int)
            return df, "_target"
        else:
            df = df.copy()
            df["_target"] = (df["transaction_status"] == "FAILED").astype(int)
            return df, "_target"

    # ------------------------------------------------------------------
    # Helper: compute Cramér's V
    # ------------------------------------------------------------------

    def _compute_cramers_v(self, df: pd.DataFrame, col_a: str, col_b: str) -> Dict[str, Any]:
        """Compute Cramér's V between two categorical columns.

        Returns dict with cramers_v, chi2, p_value, sample_size.
        """
        contingency = pd.crosstab(df[col_a], df[col_b])
        n = contingency.values.sum()
        r, c = contingency.shape

        if min(r, c) <= 1:
            return {
                "cramers_v": 0.0,
                "chi2": 0.0,
                "p_value": 1.0,
                "sample_size": int(n),
                "note": "Cramér's V undefined (min(r,c) <= 1), returned 0",
            }

        try:
            chi2, p_value, dof, expected = stats.chi2_contingency(contingency, correction=True)
        except Exception:
            return {
                "cramers_v": 0.0,
                "chi2": 0.0,
                "p_value": 1.0,
                "sample_size": int(n),
                "note": "Chi-square computation failed",
            }

        cramers_v = math.sqrt(chi2 / (n * (min(r, c) - 1)))
        return {
            "cramers_v": round(cramers_v, 4),
            "chi2": round(chi2, 4),
            "p_value": round(p_value, 10),
            "sample_size": int(n),
        }

    # ------------------------------------------------------------------
    # Helper: classify strength
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_strength(v: float) -> str:
        if v < 0.1:
            return "weak"
        elif v < 0.3:
            return "moderate"
        else:
            return "strong"

    # ------------------------------------------------------------------
    # Helper: classify effect size for r
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_effect_size(r: float) -> str:
        abs_r = abs(r)
        if abs_r < 0.1:
            return "negligible"
        elif abs_r < 0.3:
            return "small"
        elif abs_r < 0.5:
            return "medium"
        else:
            return "large"

    # ------------------------------------------------------------------
    # Helper: validate columns exist
    # ------------------------------------------------------------------

    def _validate_columns(self, columns: List[str], df: pd.DataFrame) -> Optional[str]:
        """Validate that all columns exist in the DataFrame.

        Returns error message string if validation fails, None if OK.
        """
        for col in columns:
            resolved = data_loader.resolve_column(col)
            if resolved not in df.columns:
                return f"Column '{col}' (resolved: '{resolved}') not found in dataset. Available columns: {', '.join(sorted(df.columns))}"
        return None

    # ------------------------------------------------------------------
    # ANALYSIS TYPE 1: feature_importance
    # ------------------------------------------------------------------

    def _feature_importance(self, params: dict) -> str:
        """Rank all factors by their association with a binary target."""
        target = params.get("target", "failure")
        filters = params.get("filters", [])

        df = self._apply_filters(self.df, filters)

        if len(df) < 500:
            return self._error_response(
                "feature_importance",
                f"Only {len(df)} records remain after filtering (minimum 500 recommended)",
                "Broaden your filters to include more data",
            )

        df, target_col = self._create_binary_target(df, target)
        total_records = len(df)

        categorical_cols = [
            "transaction_type", "device_type", "network_type",
            "sender_bank", "sender_age_group", "sender_state",
            "merchant_category",
        ]

        ranked_features: List[Dict] = []

        for col in categorical_cols:
            resolved = data_loader.resolve_column(col)
            if resolved not in df.columns:
                continue

            # Special handling for merchant_category (NULL for P2P)
            if col == "merchant_category":
                df_subset = df[df[resolved].notna()].copy()
                if len(df_subset) < 1000:
                    ranked_features.append({
                        "feature": col,
                        "cramers_v": 0.0,
                        "p_value": 1.0,
                        "significant": False,
                        "strength": "weak",
                        "interpretation": f"{col} skipped: only {len(df_subset)} non-null records (minimum 1000)",
                        "sample_size": len(df_subset),
                        "note": "Skipped due to insufficient non-null records",
                    })
                    continue
                result = self._compute_cramers_v(df_subset, resolved, target_col)
            else:
                result = self._compute_cramers_v(df, resolved, target_col)

            v = result["cramers_v"]
            p = result["p_value"]
            strength = self._classify_strength(v)
            significant = p < 0.05

            ranked_features.append({
                "feature": col,
                "cramers_v": v,
                "p_value": p,
                "significant": significant,
                "strength": strength,
                "interpretation": f"{col} has a {strength} association with {target} rate",
                "sample_size": result["sample_size"],
            })

        # Point-biserial for amount_inr
        amount_data = df["amount_inr"].dropna()
        target_data = df.loc[amount_data.index, target_col]
        if len(amount_data) > 1:
            try:
                r_val, p_val = stats.pointbiserialr(target_data, amount_data)
                abs_r = abs(r_val)
                strength = self._classify_strength(abs_r)
                ranked_features.append({
                    "feature": "amount_inr",
                    "cramers_v": round(abs_r, 4),
                    "p_value": round(p_val, 10),
                    "significant": p_val < 0.05,
                    "strength": strength,
                    "interpretation": f"amount_inr has a {strength} {'positive' if r_val > 0 else 'negative'} correlation with {target} rate (point-biserial r={round(r_val, 4)})",
                    "sample_size": len(amount_data),
                    "note": "Point-biserial correlation (abs value used for ranking)",
                })
            except Exception:
                ranked_features.append({
                    "feature": "amount_inr",
                    "cramers_v": 0.0,
                    "p_value": 1.0,
                    "significant": False,
                    "strength": "weak",
                    "interpretation": "amount_inr: point-biserial computation failed",
                    "sample_size": len(amount_data),
                })

        # Sort by cramers_v descending and assign ranks
        ranked_features.sort(key=lambda x: x["cramers_v"], reverse=True)
        for i, feat in enumerate(ranked_features):
            feat["rank"] = i + 1

        # Apply top_n limit
        top_n = params.get("top_n", len(ranked_features))
        ranked_features = ranked_features[:top_n]

        top_feature = ranked_features[0]["feature"] if ranked_features else "N/A"
        top_v = ranked_features[0]["cramers_v"] if ranked_features else 0

        # Build summary
        strong = [f["feature"] for f in ranked_features if f["strength"] == "strong"]
        moderate = [f["feature"] for f in ranked_features if f["strength"] == "moderate"]
        weak = [f["feature"] for f in ranked_features if f["strength"] == "weak"]
        insignificant = [f["feature"] for f in ranked_features if not f["significant"]]

        return self._to_json({
            "success": True,
            "analysis_type": "feature_importance",
            "target": target,
            "total_records": total_records,
            "ranked_features": ranked_features,
            "top_feature": top_feature,
            "key_finding": f"{top_feature} is the strongest predictor of transaction {target} (Cramér's V = {top_v})",
            "summary": {
                "strong_predictors": strong,
                "moderate_predictors": moderate,
                "weak_predictors": weak,
                "insignificant_features": insignificant,
            },
        })

    # ------------------------------------------------------------------
    # ANALYSIS TYPE 2: cramers_v_matrix
    # ------------------------------------------------------------------

    def _cramers_v_matrix(self, params: dict) -> str:
        """Compute full pairwise Cramér's V association matrix."""
        include_geography = params.get("include_geography", False)
        filters = params.get("filters", [])

        df = self._apply_filters(self.df, filters)

        if len(df) < 500:
            return self._error_response(
                "cramers_v_matrix",
                f"Only {len(df)} records remain after filtering (minimum 500 recommended)",
                "Broaden your filters to include more data",
            )

        columns = [
            "transaction_type", "device_type", "network_type",
            "sender_bank", "sender_age_group", "transaction_status",
        ]
        if include_geography:
            columns.extend(["sender_state", "merchant_category"])

        # Filter to columns that actually exist
        columns = [c for c in columns if data_loader.resolve_column(c) in df.columns]

        matrix: Dict[str, Dict[str, float]] = {c: {} for c in columns}
        all_pairs: List[Dict] = []

        for i in range(len(columns)):
            for j in range(i + 1, len(columns)):
                col_a = columns[i]
                col_b = columns[j]
                resolved_a = data_loader.resolve_column(col_a)
                resolved_b = data_loader.resolve_column(col_b)

                # Handle nulls for merchant_category
                df_pair = df.copy()
                if col_a == "merchant_category":
                    df_pair = df_pair[df_pair[resolved_a].notna()]
                if col_b == "merchant_category":
                    df_pair = df_pair[df_pair[resolved_b].notna()]

                if len(df_pair) < 100:
                    v = 0.0
                else:
                    result = self._compute_cramers_v(df_pair, resolved_a, resolved_b)
                    v = result["cramers_v"]

                matrix[col_a][col_b] = v
                matrix[col_b][col_a] = v
                all_pairs.append({
                    "pair": [col_a, col_b],
                    "cramers_v": v,
                    "strength": self._classify_strength(v),
                })

        # Sort pairs and take top 10
        all_pairs.sort(key=lambda x: x["cramers_v"], reverse=True)
        top_associations = all_pairs[:10]

        # Key finding
        if top_associations:
            best = top_associations[0]
            key_finding = (
                f"The strongest association in the dataset is between "
                f"{best['pair'][0]} and {best['pair'][1]} (V={best['cramers_v']})"
            )
        else:
            key_finding = "No associations computed"

        return self._to_json({
            "success": True,
            "analysis_type": "cramers_v_matrix",
            "columns_analyzed": columns,
            "matrix": matrix,
            "top_associations": top_associations,
            "key_finding": key_finding,
        })

    # ------------------------------------------------------------------
    # ANALYSIS TYPE 3: interaction_effects
    # ------------------------------------------------------------------

    def _interaction_effects(self, params: dict) -> str:
        """Detect two-factor interaction effects on a target rate."""
        factor_a = params.get("factor_a", "device_type")
        factor_b = params.get("factor_b", "network_type")
        target = params.get("target", "failure")
        filters = params.get("filters", [])
        min_sample_size = params.get("min_sample_size", 100)

        # Resolve column names
        factor_a = data_loader.resolve_column(factor_a)
        factor_b = data_loader.resolve_column(factor_b)

        df = self._apply_filters(self.df, filters)

        # Validate columns
        err = self._validate_columns([factor_a, factor_b], df)
        if err:
            return self._error_response("interaction_effects", err, "Use valid column names")

        if len(df) < 500:
            return self._error_response(
                "interaction_effects",
                f"Only {len(df)} records remain after filtering (minimum 500 recommended)",
                "Broaden your filters to include more data",
            )

        df, target_col = self._create_binary_target(df, target)
        overall_rate = round(df[target_col].mean() * 100, 4)

        # Step 3: Compute combinations
        grouped = df.groupby([factor_a, factor_b]).agg(
            count=(target_col, "size"),
            target_rate=(target_col, "mean"),
            total_amount_mean=("amount_inr", "mean"),
        ).reset_index()
        grouped["target_rate"] = round(grouped["target_rate"] * 100, 4)
        grouped["total_amount_mean"] = round(grouped["total_amount_mean"], 2)

        # Filter by min_sample_size
        grouped = grouped[grouped["count"] >= min_sample_size]

        if len(grouped) == 0:
            return self._error_response(
                "interaction_effects",
                f"No combinations have >= {min_sample_size} records",
                "Lower min_sample_size or broaden filters",
            )

        # Step 4: Marginal rates
        marginal_a = df.groupby(factor_a)[target_col].mean() * 100
        marginal_b = df.groupby(factor_b)[target_col].mean() * 100

        # Step 5: Compute interaction effects
        combinations: List[Dict] = []
        for _, row in grouped.iterrows():
            val_a = row[factor_a]
            val_b = row[factor_b]
            cell_rate = row["target_rate"]
            m_a = marginal_a.get(val_a, overall_rate)
            m_b = marginal_b.get(val_b, overall_rate)
            interaction = round(cell_rate - (m_a + m_b - overall_rate), 4)
            vs_overall = round(cell_rate - overall_rate, 4)

            # Rating
            if cell_rate > overall_rate * 1.2:
                rating = "high_risk"
            elif cell_rate > overall_rate * 1.05:
                rating = "moderate_risk"
            elif cell_rate >= overall_rate * 0.95:
                rating = "average"
            else:
                rating = "protective"

            combinations.append({
                "factor_a_value": str(val_a),
                "factor_b_value": str(val_b),
                "count": int(row["count"]),
                "target_rate": cell_rate,
                "interaction_effect": interaction,
                "vs_overall": vs_overall,
                "rating": rating,
            })

        combinations.sort(key=lambda x: x["target_rate"], reverse=True)

        # Build marginal effects output
        marginal_effects: Dict[str, Dict] = {
            factor_a: {},
            factor_b: {},
        }
        for val, rate in marginal_a.items():
            marginal_effects[factor_a][str(val)] = {
                "rate": round(rate, 4),
                "vs_overall": round(rate - overall_rate, 4),
            }
        for val, rate in marginal_b.items():
            marginal_effects[factor_b][str(val)] = {
                "rate": round(rate, 4),
                "vs_overall": round(rate - overall_rate, 4),
            }

        # Best/worst
        worst = combinations[0] if combinations else {}
        best = combinations[-1] if combinations else {}

        # Step 6: Chi-square interaction test
        try:
            ct = pd.crosstab([df[factor_a], df[factor_b]], df[target_col])
            chi2, p_value, _, _ = stats.chi2_contingency(ct, correction=True)
            interaction_significant = p_value < 0.05
            chi2_p_value = round(p_value, 10)
        except Exception:
            interaction_significant = False
            chi2_p_value = 1.0

        # Notable interactions: detect when factor_a ranking reverses by factor_b value
        notable_interactions: List[str] = []
        try:
            unique_b = grouped[factor_b].unique()
            if len(unique_b) >= 2:
                # For each pair of factor_b values, check if factor_a ranking reverses
                for i_b in range(len(unique_b)):
                    for j_b in range(i_b + 1, len(unique_b)):
                        b1 = unique_b[i_b]
                        b2 = unique_b[j_b]
                        sub1 = grouped[grouped[factor_b] == b1].set_index(factor_a)["target_rate"]
                        sub2 = grouped[grouped[factor_b] == b2].set_index(factor_a)["target_rate"]
                        common = sub1.index.intersection(sub2.index)
                        if len(common) >= 2:
                            # Check if the best factor_a value in one factor_b is worst in another
                            rank1 = sub1[common].rank()
                            rank2 = sub2[common].rank()
                            for a_val in common:
                                for a_val2 in common:
                                    if a_val == a_val2:
                                        continue
                                    # a_val is better in b1 but worse in b2 (or vice versa)
                                    if (sub1[a_val] < sub1[a_val2]) and (sub2[a_val] > sub2[a_val2]):
                                        notable_interactions.append(
                                            f"{b1} favors {a_val} ({target} rate {sub1[a_val]:.1f}% vs {sub1[a_val2]:.1f}%), "
                                            f"but {b2} reverses: {a_val} has {sub2[a_val]:.1f}% vs {a_val2} at {sub2[a_val2]:.1f}%"
                                        )
                                        if len(notable_interactions) >= 3:
                                            break
                                if len(notable_interactions) >= 3:
                                    break
                        if len(notable_interactions) >= 3:
                            break
                    if len(notable_interactions) >= 3:
                        break
        except Exception:
            pass

        key_finding = (
            f"{worst.get('factor_a_value', 'N/A')} + {worst.get('factor_b_value', 'N/A')} "
            f"is the worst combination with {worst.get('target_rate', 0)}% {target} rate, "
            f"which is {worst.get('interaction_effect', 0)} percentage points worse than "
            f"factors acting independently would predict"
        )

        return self._to_json({
            "success": True,
            "analysis_type": "interaction_effects",
            "factor_a": factor_a,
            "factor_b": factor_b,
            "target": target,
            "overall_rate": overall_rate,
            "combinations": combinations,
            "marginal_effects": marginal_effects,
            "worst_combination": {
                "factor_a_value": worst.get("factor_a_value", "N/A"),
                "factor_b_value": worst.get("factor_b_value", "N/A"),
                "target_rate": worst.get("target_rate", 0),
            },
            "best_combination": {
                "factor_a_value": best.get("factor_a_value", "N/A"),
                "factor_b_value": best.get("factor_b_value", "N/A"),
                "target_rate": best.get("target_rate", 0),
            },
            "interaction_significant": interaction_significant,
            "chi2_p_value": chi2_p_value,
            "key_finding": key_finding,
            "notable_interactions": notable_interactions[:3],
        })

    # ------------------------------------------------------------------
    # ANALYSIS TYPE 4: multivariate_combination
    # ------------------------------------------------------------------

    def _multivariate_combination(self, params: dict) -> str:
        """Find riskiest/safest combinations of 2-4 factors simultaneously."""
        factors = params.get("factors", ["sender_bank", "device_type", "network_type"])
        target = params.get("target", "failure")
        top_n = params.get("top_n", 15)
        min_sample_size = params.get("min_sample_size", 200)
        filters = params.get("filters", [])

        if len(factors) < 2 or len(factors) > 4:
            return self._error_response(
                "multivariate_combination",
                f"factors must contain 2-4 columns, got {len(factors)}",
                "Provide 2-4 column names in the factors list",
            )

        # Resolve column names
        resolved_factors = [data_loader.resolve_column(f) for f in factors]

        df = self._apply_filters(self.df, filters)

        # Validate columns
        err = self._validate_columns(resolved_factors, df)
        if err:
            return self._error_response("multivariate_combination", err, "Use valid column names")

        if len(df) < 500:
            return self._error_response(
                "multivariate_combination",
                f"Only {len(df)} records remain after filtering (minimum 500 recommended)",
                "Broaden your filters to include more data",
            )

        df, target_col = self._create_binary_target(df, target)
        overall_rate = round(df[target_col].mean() * 100, 4)

        # Group by all factors
        agg_dict = {
            target_col: ["size", "mean"],
            "amount_inr": ["mean", "sum"],
            "fraud_flag": ["mean"],
        }
        # Also compute success rate separately
        df_temp = df.copy()
        df_temp["_is_success"] = (df_temp["transaction_status"] == "SUCCESS").astype(int)

        grouped = df_temp.groupby(resolved_factors).agg(
            count=(target_col, "size"),
            target_rate=(target_col, "mean"),
            avg_amount=("amount_inr", "mean"),
            total_amount=("amount_inr", "sum"),
            fraud_rate=("fraud_flag", "mean"),
            success_rate=("_is_success", "mean"),
        ).reset_index()

        grouped["target_rate"] = round(grouped["target_rate"] * 100, 4)
        grouped["fraud_rate"] = round(grouped["fraud_rate"] * 100, 4)
        grouped["success_rate"] = round(grouped["success_rate"] * 100, 4)
        grouped["avg_amount"] = round(grouped["avg_amount"], 2)
        grouped["total_amount"] = round(grouped["total_amount"], 2)

        total_combinations_found = len(grouped)
        if total_combinations_found > 500:
            print(f"  ⚠️ multivariate_combination: {total_combinations_found} combinations found (>500)")

        # Filter by min_sample_size
        grouped = grouped[grouped["count"] >= min_sample_size]

        if len(grouped) == 0:
            return self._error_response(
                "multivariate_combination",
                f"No combinations have >= {min_sample_size} records after filtering",
                "Lower min_sample_size or remove some factors",
            )

        # Sort by target_rate descending
        grouped = grouped.sort_values("target_rate", ascending=False).reset_index(drop=True)

        def _build_combo(row: pd.Series) -> Dict:
            combo = {f: str(row[f]) for f in resolved_factors}
            combo_label = " + ".join(str(row[f]) for f in resolved_factors)
            vs_baseline = round(row["target_rate"] - overall_rate, 4)
            risk_multiplier = round(row["target_rate"] / overall_rate, 2) if overall_rate > 0 else 0
            return {
                "combination": combo,
                "combination_label": combo_label,
                "count": int(row["count"]),
                "target_rate": row["target_rate"],
                "vs_baseline": vs_baseline,
                "success_rate": row["success_rate"],
                "avg_amount": row["avg_amount"],
                "fraud_rate": row["fraud_rate"],
                "risk_multiplier": risk_multiplier,
            }

        # Top riskiest
        riskiest_rows = grouped.head(top_n)
        riskiest_combinations: List[Dict] = []
        for rank_idx, (_, row) in enumerate(riskiest_rows.iterrows()):
            entry = _build_combo(row)
            entry["rank"] = rank_idx + 1
            riskiest_combinations.append(entry)

        # Safest
        safest_rows = grouped.tail(top_n).sort_values("target_rate", ascending=True).reset_index(drop=True)
        safest_combinations: List[Dict] = []
        for rank_idx, (_, row) in enumerate(safest_rows.iterrows()):
            entry = _build_combo(row)
            entry["rank"] = rank_idx + 1
            safest_combinations.append(entry)

        # Pattern insights
        pattern_insights = self._generate_pattern_insights(
            riskiest_combinations, safest_combinations, resolved_factors, target
        )

        # Key finding
        if riskiest_combinations:
            top_risk = riskiest_combinations[0]
            key_finding = (
                f"{top_risk['combination_label']} is the riskiest combination with "
                f"{top_risk['target_rate']}% {target} rate — "
                f"{top_risk['risk_multiplier']}x the baseline of {overall_rate}%"
            )
        else:
            key_finding = "No valid combinations found"

        return self._to_json({
            "success": True,
            "analysis_type": "multivariate_combination",
            "factors": resolved_factors,
            "target": target,
            "total_combinations_found": total_combinations_found,
            "overall_baseline_rate": overall_rate,
            "riskiest_combinations": riskiest_combinations,
            "safest_combinations": safest_combinations,
            "key_finding": key_finding,
            "pattern_insights": pattern_insights,
        })

    def _generate_pattern_insights(
        self,
        riskiest: List[Dict],
        safest: List[Dict],
        factors: List[str],
        target: str,
    ) -> List[str]:
        """Programmatically scan for disproportionate factor values in riskiest vs safest."""
        insights: List[str] = []
        top_k = min(5, len(riskiest))
        bottom_k = min(5, len(safest))

        for factor in factors:
            factor_label = factor.replace("_", " ")
            # Count occurrences in top-5 riskiest
            risky_vals: Dict[str, int] = {}
            for entry in riskiest[:top_k]:
                val = entry["combination"].get(factor, "")
                risky_vals[val] = risky_vals.get(val, 0) + 1

            safe_vals: Dict[str, int] = {}
            for entry in safest[:bottom_k]:
                val = entry["combination"].get(factor, "")
                safe_vals[val] = safe_vals.get(val, 0) + 1

            # Disproportionate in risky
            for val, count in risky_vals.items():
                if count >= 3:
                    insights.append(
                        f"{val} appears in {count} of the top {top_k} riskiest combinations"
                    )
            # Disproportionate in safe
            for val, count in safe_vals.items():
                if count >= 3:
                    insights.append(
                        f"{val} appears in {count} of the top {bottom_k} safest combinations"
                    )

        return insights[:5]

    # ------------------------------------------------------------------
    # ANALYSIS TYPE 5: point_biserial
    # ------------------------------------------------------------------

    def _point_biserial(self, params: dict) -> str:
        """Point-biserial correlation between a continuous and a binary variable."""
        continuous_var = params.get("continuous_var", "amount_inr")
        binary_target = params.get("binary_target", "fraud")
        filters = params.get("filters", [])
        include_distribution = params.get("include_distribution", True)
        segment_by = params.get("segment_by", None)

        continuous_var = data_loader.resolve_column(continuous_var)

        df = self._apply_filters(self.df, filters)

        err = self._validate_columns([continuous_var], df)
        if err:
            return self._error_response("point_biserial", err, "Use a valid continuous column")

        if len(df) < 500:
            return self._error_response(
                "point_biserial",
                f"Only {len(df)} records remain after filtering (minimum 500 recommended)",
                "Broaden your filters to include more data",
            )

        df, target_col = self._create_binary_target(df, binary_target)

        # Drop nulls in both columns
        df_clean = df[[continuous_var, target_col]].dropna()
        total_records = len(df_clean)

        if total_records < 10:
            return self._error_response(
                "point_biserial",
                "Too few valid records after dropping nulls",
                "Check data quality or broaden filters",
            )

        # Compute point-biserial
        try:
            r_val, p_val = stats.pointbiserialr(df_clean[target_col], df_clean[continuous_var])
        except Exception as exc:
            return self._error_response(
                "point_biserial",
                f"Point-biserial computation failed: {exc}",
                "Ensure the continuous variable has variance",
            )

        r_val = round(float(r_val), 4)
        p_val = round(float(p_val), 10)
        direction = "positive" if r_val > 0 else "negative"
        effect_size = self._classify_effect_size(r_val)
        significant = p_val < 0.05

        # Cohen's d
        group_1 = df_clean[df_clean[target_col] == 1][continuous_var]
        group_0 = df_clean[df_clean[target_col] == 0][continuous_var]
        mean_1 = float(group_1.mean()) if len(group_1) > 0 else 0.0
        mean_0 = float(group_0.mean()) if len(group_0) > 0 else 0.0
        std_1 = float(group_1.std()) if len(group_1) > 1 else 0.0
        std_0 = float(group_0.std()) if len(group_0) > 1 else 0.0
        pooled_std = math.sqrt((std_1 ** 2 + std_0 ** 2) / 2) if (std_1 + std_0) > 0 else 1.0
        cohens_d = round((mean_1 - mean_0) / pooled_std, 4) if pooled_std > 0 else 0.0

        # Target labels for output
        target_labels = {
            "fraud": ("fraud_flagged", "not_fraud_flagged"),
            "failure": ("failed", "not_failed"),
            "success": ("successful", "not_successful"),
        }
        label_1, label_0 = target_labels.get(binary_target, ("target_1", "target_0"))

        result: Dict[str, Any] = {
            "success": True,
            "analysis_type": "point_biserial",
            "continuous_var": continuous_var,
            "binary_target": binary_target,
            "total_records": total_records,
            "correlation": {
                "r": r_val,
                "p_value": p_val,
                "significant": significant,
                "direction": direction,
                "effect_size": effect_size,
                "interpretation": (
                    f"{'Higher' if r_val > 0 else 'Lower'} {continuous_var.replace('_', ' ')} "
                    f"values are {'weakly ' if effect_size in ('negligible', 'small') else ''}"
                    f"associated with higher {binary_target} rates"
                ),
            },
            "cohens_d": cohens_d,
        }

        # Group distributions
        if include_distribution:
            def _dist_stats(s: pd.Series) -> Dict:
                if len(s) == 0:
                    return {"count": 0, "mean": 0, "median": 0, "std": 0, "p25": 0, "p75": 0}
                return {
                    "count": int(len(s)),
                    "mean": round(float(s.mean()), 2),
                    "median": round(float(s.median()), 2),
                    "std": round(float(s.std()), 2),
                    "p25": round(float(s.quantile(0.25)), 2),
                    "p75": round(float(s.quantile(0.75)), 2),
                }

            result["group_distributions"] = {
                label_1: _dist_stats(group_1),
                label_0: _dist_stats(group_0),
            }

        # Segmented results
        if segment_by:
            segment_by = data_loader.resolve_column(segment_by)
            if segment_by in df.columns:
                segmented_results: Dict[str, Any] = {}
                for seg_val in df[segment_by].dropna().unique():
                    seg_df = df_clean.merge(
                        df[[segment_by]].loc[df_clean.index],
                        left_index=True,
                        right_index=True,
                        how="inner",
                    )
                    seg_subset = seg_df[seg_df[segment_by] == seg_val]
                    if len(seg_subset) < 10:
                        continue
                    try:
                        seg_r, seg_p = stats.pointbiserialr(
                            seg_subset[target_col], seg_subset[continuous_var]
                        )
                        segmented_results[str(seg_val)] = {
                            "r": round(float(seg_r), 4),
                            "p_value": round(float(seg_p), 10),
                            "significant": seg_p < 0.05,
                            "direction": "positive" if seg_r > 0 else "negative",
                            "effect_size": self._classify_effect_size(seg_r),
                            "sample_size": len(seg_subset),
                        }
                    except Exception:
                        continue
                result["segmented_results"] = segmented_results

        # Key finding
        result["key_finding"] = (
            f"{label_1.replace('_', ' ').title()} transactions have a mean amount of "
            f"₹{mean_1:,.0f} vs ₹{mean_0:,.0f} for {label_0.replace('_', ' ')} — "
            f"a {'statistically significant' if significant else 'not statistically significant'} "
            f"difference (r={r_val}, p{'<0.001' if p_val < 0.001 else '=' + str(round(p_val, 4))})"
        )

        return self._to_json(result)

    # ------------------------------------------------------------------
    # Error response helper
    # ------------------------------------------------------------------

    def _error_response(self, analysis_type: str, error: str, suggestion: str) -> str:
        """Build standardised error JSON response."""
        return self._to_json({
            "success": False,
            "analysis_type": analysis_type,
            "error": error,
            "suggestion": suggestion,
        })


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

def create_correlation_tool() -> StructuredTool:
    """
    Factory function to create the correlation & feature importance tool for LangChain.

    Returns:
        StructuredTool configured for correlation and feature importance analysis.
    """
    tool_instance = CorrelationTool()

    return StructuredTool.from_function(
        func=tool_instance.analyze,
        name="correlation_importance_tool",
        description=(
            "Analyze which factors most strongly influence transaction failure rate, "
            "fraud rate, or other outcomes. Use for feature importance rankings, "
            "Cramér's V association matrix, interaction effects between two categorical "
            "factors, multivariate combination analysis (which combination of bank + "
            "device + network has highest failure), and point-biserial correlation "
            "between amount and fraud. Input: analysis_type (string) and parameters "
            "(JSON string)."
        ),
        args_schema=CorrelationInput,
    )
