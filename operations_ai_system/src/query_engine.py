"""Intent parsing and deterministic pandas query execution."""

import difflib
from dataclasses import dataclass

import pandas as pd

from src.data_loader import (
    WEEK_LABELS,
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
    ) -> None:
        self.llm = llm
        self.df_metrics = df_metrics
        self.df_orders = df_orders
        self.valid_metrics = get_valid_metrics(df_metrics)
        self.schema_context = get_schema_summary(df_metrics, df_orders)

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
            intent["weeks"] = 8
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
        """Apply geographic and classification filters from intent."""
        if intent.get("country"):
            df = df[df["COUNTRY"] == intent["country"]]
        if intent.get("city"):
            df = df[df["CITY"].str.contains(intent["city"], case=False, na=False)]
        if intent.get("zone"):
            df = df[df["ZONE"].str.contains(intent["zone"], case=False, na=False)]
        if intent.get("zone_type"):
            df = df[df["ZONE_TYPE"] == intent["zone_type"]]
        if intent.get("zone_prioritization"):
            df = df[df["ZONE_PRIORITIZATION"] == intent["zone_prioritization"]]
        return df

    def _week_columns(self, weeks: int) -> list[str]:
        """Return the last N week column names."""
        all_weeks = WEEK_LABELS  # L8W, L7W, ..., L0W
        return all_weeks[-weeks:]

    def _execute_filter_rank(self, intent: dict) -> QueryResult:
        """Top/bottom N zones by a metric."""
        metric = intent["metric"]
        top_n = intent.get("top_n", 10)
        ascending = intent.get("sort_order") == "asc"

        df = self.df_metrics[self.df_metrics["METRIC"] == metric].copy()
        df = self._apply_filters(df, intent)

        df = df.sort_values("L0W", ascending=ascending).head(top_n)
        result = df[["COUNTRY", "CITY", "ZONE", "ZONE_TYPE", "L0W"]].copy()
        result = result.rename(columns={"L0W": metric})

        return QueryResult(
            df=result,
            query_type="filter_rank",
            metric=metric,
            intent=intent,
            chart_type="bar" if intent.get("generate_chart") else None,
        )

    def _execute_compare(self, intent: dict) -> QueryResult:
        """Compare metric grouped by zone_type or country."""
        metric = intent["metric"]
        group_by = intent.get("group_by", "zone_type")

        df = self.df_metrics[self.df_metrics["METRIC"] == metric].copy()
        df = self._apply_filters(df, intent)

        group_col = "ZONE_TYPE" if group_by == "zone_type" else "COUNTRY"
        result = df.groupby(group_col)["L0W"].mean().reset_index()
        result = result.rename(columns={"L0W": metric})
        result = result.sort_values(metric, ascending=False)

        return QueryResult(
            df=result,
            query_type="compare",
            metric=metric,
            intent=intent,
            chart_type="bar",
        )

    def _execute_trend(self, intent: dict) -> QueryResult:
        """Metric evolution over weeks for a specific zone."""
        metric = intent["metric"]
        weeks = intent.get("weeks", 8)
        week_cols = self._week_columns(weeks)

        df = self.df_metrics[self.df_metrics["METRIC"] == metric].copy()
        df = self._apply_filters(df, intent)

        if df.empty:
            return QueryResult(
                df=pd.DataFrame(), query_type="trend", metric=metric, intent=intent
            )

        id_cols = ["COUNTRY", "CITY", "ZONE"]
        result = df[id_cols + week_cols].melt(
            id_vars=id_cols,
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
        """Metric average/median grouped by country or zone_type."""
        metric = intent["metric"]
        group_by = intent.get("group_by", "country")

        df = self.df_metrics[self.df_metrics["METRIC"] == metric].copy()
        df = self._apply_filters(df, intent)

        group_col = "COUNTRY" if group_by == "country" else "ZONE_TYPE"
        result = df.groupby(group_col)["L0W"].agg(["mean", "median", "count"]).reset_index()
        result = result.rename(columns={"mean": f"{metric} (avg)", "median": f"{metric} (median)"})
        result = result.sort_values(f"{metric} (avg)", ascending=False)

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

        df = self.df_metrics[self.df_metrics["METRIC"].isin([metric_a, metric_b])].copy()
        df = self._apply_filters(df, intent)

        pivot = df.pivot_table(
            index=["COUNTRY", "CITY", "ZONE"],
            columns="METRIC",
            values="L0W",
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
        """Zones with highest order growth over recent weeks."""
        weeks = intent.get("weeks", 5)
        top_n = intent.get("top_n", 10)
        ascending = intent.get("sort_order") == "asc"
        week_cols = self._week_columns(weeks)

        df = self.df_orders.copy()
        df = self._apply_filters(df, intent)

        first_col = week_cols[0]
        last_col = week_cols[-1]

        df["growth_pct"] = (df[last_col] - df[first_col]) / df[first_col].replace(0, float("nan"))
        df = df.sort_values("growth_pct", ascending=ascending).head(top_n)

        result = df[["COUNTRY", "CITY", "ZONE", first_col, last_col, "growth_pct"]].copy()
        result = result.rename(columns={
            first_col: f"Orders ({first_col})",
            last_col: f"Orders ({last_col})",
        })
        result["growth_pct"] = (result["growth_pct"] * 100).round(2)

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
        if result.df.empty:
            return "No data found for this query. Try adjusting the filters or rephrasing the question."

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
        )
        return self.llm.suggest_followups(prompt)
