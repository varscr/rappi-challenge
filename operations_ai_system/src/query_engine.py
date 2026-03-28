"""Intent parsing and deterministic pandas query execution."""

import difflib
from dataclasses import dataclass

import pandas as pd

from src.data_loader import (
    get_dimension_columns,
    get_metric_column,
    get_schema_summary,
    get_valid_metrics,
)
from src.llm_client import LLMClient
from src.prompts import (
    INTENT_PARSER_SYSTEM_PROMPT,
    RESPONSE_NARRATOR_PROMPT,
    SUGGESTION_PROMPT,
)


@dataclass
class QueryResult:
    """Container for a query execution result."""

    df: pd.DataFrame
    query_type: str
    metric: str | list[str]
    intent: dict
    chart_type: str | None = None  # "line", "bar", or None


class QueryEngine:
    """Orchestrates intent parsing, query execution, and response narration."""

    def __init__(
        self,
        llm: LLMClient,
        df_metrics: pd.DataFrame,
        df_orders: pd.DataFrame,
        week_labels: list[str],
    ) -> None:
        self.llm = llm
        self.df_metrics = df_metrics
        self.df_orders = df_orders
        self.week_labels = week_labels
        self.current_week = week_labels[-1] if week_labels else "L0W"
        self.dimensions = get_dimension_columns(df_metrics, week_labels)
        self.metric_col = get_metric_column(df_metrics)
        
        self.valid_metrics = get_valid_metrics(df_metrics)
        self.schema_context = get_schema_summary(df_metrics, df_orders, week_labels)

        self._executors = {
            "filter_rank": self._execute_filter_rank,
            "compare": self._execute_compare,
            "trend": self._execute_trend,
            "aggregate": self._execute_aggregate,
            "multivariable": self._execute_multivariable,
            "order_growth": self._execute_order_growth,
        }

    # ── Public API ──────────────────────────────────────────────────

    def process_question(self, question: str) -> tuple[QueryResult, str, list[str]]:
        """Full pipeline: question → intent → execute → narrate → suggestions.

        Returns:
            (query_result, narration_text, follow_up_suggestions)
        """
        intent = self._parse_intent(question)
        result = self._execute(intent)
        narration = self._narrate(question, result)
        suggestions = self._suggest(question, intent)
        
        # Add to memory for true conversational flow
        self.llm.memory.add("user", question)
        self.llm.memory.add("assistant", narration)
        self.llm.memory.last_intent = intent
        
        return result, narration, suggestions

    # ── Intent Parsing ──────────────────────────────────────────────

    def _parse_intent(self, question: str) -> dict:
        """Parse user question into structured intent via LLM."""
        last_intent = self.llm.memory.last_intent or {}
        metrics_list = "\n".join(f"- {m}" for m in self.valid_metrics)

        system_prompt = INTENT_PARSER_SYSTEM_PROMPT.format(
            schema_context=self.schema_context,
            metrics_list=metrics_list,
            last_intent=last_intent,
        )

        intent = self.llm.parse_intent(system_prompt, question)
        intent = self._validate_intent(intent)
        return intent

    def _validate_intent(self, intent: dict) -> dict:
        """Validate and fix metric names via fuzzy matching."""
        metric = intent.get("metric")
        if isinstance(metric, str):
            intent["metric"] = self._fuzzy_match_metric(metric)
        elif isinstance(metric, list):
            intent["metric"] = [self._fuzzy_match_metric(m) for m in metric]

        if "weeks" not in intent or intent["weeks"] is None:
            intent["weeks"] = len(self.week_labels)
        if "sort_order" not in intent or intent["sort_order"] is None:
            intent["sort_order"] = "desc"

        return intent

    def _fuzzy_match_metric(self, name: str) -> str:
        """Match a metric name to the closest valid metric."""
        if name in self.valid_metrics:
            return name
        matches = difflib.get_close_matches(name, self.valid_metrics, n=1, cutoff=0.4)
        if matches:
            return matches[0]
        return name

    # ── Query Execution ─────────────────────────────────────────────

    def _execute(self, intent: dict) -> QueryResult:
        """Route intent to the appropriate executor."""
        query_type = intent.get("query_type", "unknown")
        executor = self._executors.get(query_type)
        if not executor:
            return QueryResult(
                df=pd.DataFrame(),
                query_type="unknown",
                metric=intent.get("metric", ""),
                intent=intent,
            )
        return executor(intent)

    def _apply_filters(self, df: pd.DataFrame, intent: dict) -> pd.DataFrame:
        """Apply filters dynamically based on the intent's filters object."""
        filters = intent.get("filters", {})
        if not isinstance(filters, dict):
            return df
            
        for dim, value in filters.items():
            if dim in self.dimensions and value:
                # Use str.contains for partial matches, exactly for others
                if pd.api.types.is_string_dtype(df[dim]):
                     df = df[df[dim].str.contains(str(value), case=False, na=False)]
                else:
                     df = df[df[dim] == value]
        return df

    def _week_columns(self, weeks: int) -> list[str]:
        """Return the last N week column names."""
        return self.week_labels[-weeks:]

    def _execute_filter_rank(self, intent: dict) -> QueryResult:
        """Top/bottom N zones by a metric."""
        metric = intent["metric"]
        top_n = intent.get("top_n", 10)
        ascending = intent.get("sort_order") == "asc"

        df = self.df_metrics[self.df_metrics[self.metric_col] == metric].copy()
        df = self._apply_filters(df, intent)

        df = df.sort_values(self.current_week, ascending=ascending).head(top_n)
        
        # Include all dimensions up to the display column for context
        cols_to_keep = self.dimensions + [self.current_week]
        result = df[cols_to_keep].copy()
        result = result.rename(columns={self.current_week: metric})

        return QueryResult(
            df=result,
            query_type="filter_rank",
            metric=metric,
            intent=intent,
            chart_type="bar" if intent.get("generate_chart") else None,
        )

    def _execute_compare(self, intent: dict) -> QueryResult:
        """Compare metric grouped by a dynamic dimension."""
        metric = intent["metric"]
        group_by = intent.get("group_by")
        
        if group_by not in self.dimensions:
             # Default to the second-highest dimension (often CITY or ZONE_TYPE)
             group_by = self.dimensions[min(1, len(self.dimensions)-1)] if self.dimensions else "Index"

        df = self.df_metrics[self.df_metrics[self.metric_col] == metric].copy()
        df = self._apply_filters(df, intent)

        if group_by not in df.columns:
            return QueryResult(df=pd.DataFrame(), query_type="compare", metric=metric, intent=intent)

        result = df.groupby(group_by)[self.current_week].mean().reset_index()
        result = result.rename(columns={self.current_week: metric})
        result = result.sort_values(metric, ascending=False)

        return QueryResult(
            df=result,
            query_type="compare",
            metric=metric,
            intent=intent,
            chart_type="bar",
        )

    def _execute_trend(self, intent: dict) -> QueryResult:
        """Metric evolution over weeks for a specific filter."""
        metric = intent["metric"]
        weeks = intent.get("weeks", len(self.week_labels))
        week_cols = self._week_columns(weeks)

        df = self.df_metrics[self.df_metrics[self.metric_col] == metric].copy()
        df = self._apply_filters(df, intent)

        if df.empty:
            return QueryResult(
                df=pd.DataFrame(), query_type="trend", metric=metric, intent=intent
            )

        result = df[self.dimensions + week_cols].melt(
            id_vars=self.dimensions,
            value_vars=week_cols,
            var_name="Week",
            value_name=metric,
        )

        return QueryResult(
            df=result,
            query_type="trend",
            metric=metric,
            intent=intent,
            chart_type="line",
        )

    def _execute_aggregate(self, intent: dict) -> QueryResult:
        """Metric average/median grouped by a dimension."""
        metric = intent["metric"]
        group_by = intent.get("group_by")
        
        if group_by not in self.dimensions:
             # Default to the highest dimension (often COUNTRY)
             group_by = self.dimensions[0] if self.dimensions else "Index"

        df = self.df_metrics[self.df_metrics[self.metric_col] == metric].copy()
        df = self._apply_filters(df, intent)

        if group_by not in df.columns:
             return QueryResult(df=pd.DataFrame(), query_type="aggregate", metric=metric, intent=intent)

        result = df.groupby(group_by)[self.current_week].agg(["mean", "median", "count"]).reset_index()
        result = result.rename(columns={
            "mean": f"{metric} (promedio)", 
            "median": f"{metric} (mediana)",
            "count": "Conteo de registros"
        })
        result = result.sort_values(f"{metric} (promedio)", ascending=False)

        return QueryResult(
            df=result,
            query_type="aggregate",
            metric=metric,
            intent=intent,
            chart_type="bar" if intent.get("generate_chart") else None,
        )

    def _execute_multivariable(self, intent: dict) -> QueryResult:
        """Zones meeting conditions on two metrics simultaneously."""
        metrics = intent["metric"]
        if not isinstance(metrics, list) or len(metrics) < 2:
            return QueryResult(
                df=pd.DataFrame(),
                query_type="multivariable",
                metric=metrics,
                intent=intent,
            )

        metric_a, metric_b = metrics[0], metrics[1]

        df = self.df_metrics[self.df_metrics[self.metric_col].isin([metric_a, metric_b])].copy()
        df = self._apply_filters(df, intent)

        pivot = df.pivot_table(
            index=self.dimensions,
            columns=self.metric_col,
            values=self.current_week,
        ).reset_index()

        if metric_a not in pivot.columns or metric_b not in pivot.columns:
            return QueryResult(
                df=pd.DataFrame(),
                query_type="multivariable",
                metric=metrics,
                intent=intent,
            )

        median_a = pivot[metric_a].median()
        median_b = pivot[metric_b].median()

        conditions = intent.get("conditions", {})
        cond_a = conditions.get(metric_a, "high")
        cond_b = conditions.get(metric_b, "low")

        mask_a = pivot[metric_a] >= median_a if cond_a == "high" else pivot[metric_a] < median_a
        mask_b = pivot[metric_b] >= median_b if cond_b == "high" else pivot[metric_b] < median_b

        result = pivot[mask_a & mask_b].sort_values(metric_a, ascending=False)
        top_n = intent.get("top_n", 10)
        result = result.head(top_n)

        return QueryResult(
            df=result,
            query_type="multivariable",
            metric=metrics,
            intent=intent,
        )

    def _execute_order_growth(self, intent: dict) -> QueryResult:
        """Zones with highest order growth + explanations from other metrics."""
        weeks = intent.get("weeks", 5)
        top_n = intent.get("top_n", 10)
        ascending = intent.get("sort_order") == "asc"
        week_cols = self._week_columns(weeks)

        df = self.df_orders.copy()
        df = self._apply_filters(df, intent)

        if not week_cols or len(week_cols) < 2:
            return QueryResult(df=pd.DataFrame(), query_type="order_growth", metric="Orders", intent=intent)

        first_col = week_cols[0]
        last_col = week_cols[-1]

        # 1. Calculate Growth
        df["growth_pct"] = (df[last_col] - df[first_col]) / df[first_col].replace(0, float("nan"))
        df = df.sort_values("growth_pct", ascending=ascending).head(top_n)
        
        # 2. Add "Explainer" Metrics
        # Pivot the metrics table for the current week to get explanatory features
        explainer_pivot = self.df_metrics.pivot_table(
            index=self.dimensions,
            columns=self.metric_col,
            values=self.current_week
        ).reset_index()
        
        # Select top explanatory metrics (e.g., Lead Penetration, Pro Adoption)
        top_explainer_metrics = ["Lead Penetration", "Pro Adoption", "Perfect Orders"]
        available_explainers = [m for m in top_explainer_metrics if m in explainer_pivot.columns]
        
        # Join growth data with explanatory metrics
        order_dims = [d for d in self.dimensions if d in df.columns]
        result = df.merge(explainer_pivot[order_dims + available_explainers], on=order_dims, how="left")

        # 3. Finalize result columns
        cols_to_keep = order_dims + [first_col, last_col, "growth_pct"] + available_explainers
        result = result[cols_to_keep].copy()
        
        result = result.rename(columns={
            first_col: f"Órdenes ({first_col})",
            last_col: f"Órdenes ({last_col})",
            "growth_pct": "% Crecimiento"
        })
        result["% Crecimiento"] = (result["% Crecimiento"] * 100).round(2)

        return QueryResult(
            df=result,
            query_type="order_growth",
            metric="Orders",
            intent=intent,
            chart_type="bar" if intent.get("generate_chart") else None,
        )

    # ── Response Narration ──────────────────────────────────────────

    def _narrate(self, question: str, result: QueryResult) -> str:
        """Generate business-language narration of the result."""
        # IF query type is unknown, it's likely a conversational meta-question
        if result.query_type == "unknown":
            return self.llm.chat(question)

        if result.df.empty:
            return "No se encontraron datos para esta consulta. Intenta ajustar los filtros o replantear la pregunta."

        table_str = result.df.head(15).to_string(index=False)
        prompt = RESPONSE_NARRATOR_PROMPT.format(
            user_question=question,
            query_result=table_str,
        )
        return self.llm.narrate(prompt)

    def _suggest(self, question: str, intent: dict) -> list[str]:
        """Generate follow-up question suggestions."""
        prompt = SUGGESTION_PROMPT.format(
            user_question=question,
            query_type=intent.get("query_type", ""),
            metric=intent.get("metric", ""),
            weeks_count=len(self.week_labels),
            dimensions_list=", ".join(self.dimensions),
        )
        return self.llm.suggest_followups(prompt)
