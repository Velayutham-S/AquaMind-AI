import time
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import SessionLocal
from app.agents.state import AgentState
from app.logging_config import logger
from app.agents.location_resolver import LocationResolver
from app.agents.query_builder import QueryBuilder
from app.agents.data_validator import DataValidator
from app.agents.statistics_engine import StatisticsEngine
from app.agents.chart_builder import ChartBuilder
from app.agents.table_formatter import TableFormatter
from app.agents.data_confidence import DataConfidence
from app.agents.data_citations import DataCitations
from app.agents.data_metrics import DataMetrics

class DataAgent:
    """Deterministic, high-performance Data Agent serving all SQL groundwater queries with zero LLM usage."""

    # Baseline metadata mappings
    COLUMNS_MAP = {
        "district_assessments": {
            "district": "District",
            "year": "Year",
            "total_recharge": "Recharge (ham)",
            "annual_extractable": "Extractable (ham)",
            "total_extraction": "Extraction (ham)",
            "stage_of_extraction": "Extraction Stage (%)",
            "category": "Category"
        },
        "firka_assessments": {
            "district": "District",
            "firka": "Firka",
            "year": "Year",
            "total_recharge": "Recharge (ham)",
            "annual_extractable": "Extractable (ham)",
            "total_extraction": "Extraction (ham)",
            "stage_of_extraction": "Extraction Stage (%)",
            "category": "Category"
        },
        "monitoring_data": {
            "station": "Station",
            "district": "District",
            "village": "Village",
            "parameter": "Parameter",
            "acquisition_time": "Time",
            "value": "Water Level (m)",
            "unit": "Unit"
        }
    }

    @staticmethod
    def process(state: AgentState) -> dict:
        """Process entry point executing the structured validator, builder, stats, and visualization pipeline."""
        metrics_tracker = DataMetrics.start_tracking()
        start_build = time.time()
        
        query = state.get("query")
        original_query = state.get("original_query", query)
        resolved_location = state.get("resolved_location")
        resolved_location_type = state.get("resolved_location_type")
        resolved_year = state.get("resolved_year")
        intent = state.get("intent", "data")
        response_type = state.get("response_type", "text")
        session_id = state.get("session_id", "default")
        
        logger.info(f"DataAgent processing query: '{query}' | Location: {resolved_location} ({resolved_location_type})")
        
        db = SessionLocal()
        
        try:
            # 1. Resolve Location dynamically if not pre-resolved
            is_exact = True
            if not resolved_location or not resolved_location_type:
                # Use query string or extract from query
                res_loc = LocationResolver.resolve_location(db, query)
                resolved_location = res_loc["resolved"]
                resolved_location_type = res_loc["type"]
                is_exact = False
                
            # 2. Input Validation
            is_valid, err_msg = DataValidator.validate_query_entities(
                location=resolved_location,
                location_type=resolved_location_type,
                year=resolved_year
            )
            if not is_valid:
                logger.warning(f"DataAgent validation failed: {err_msg}")
                db.close()
                metrics = DataMetrics.stop_tracking(None, None, {}, metrics_tracker, 0)
                return {
                    "context_data": [],
                    "confidence_score": 0.0,
                    "confidence_reason": f"Validation failed: {err_msg}",
                    "response": f"⚠️ **Data query failed:** {err_msg}"
                }
                
            # 3. Determine database target table and select fields
            table_name = "district_assessments"
            select_fields = ["id", "district", "year", "total_recharge", "annual_extractable", "total_extraction", "stage_of_extraction", "category"]
            filters = {}
            joins = None
            group_by = None
            order_by = "year ASC"
            
            # Map location scopes
            if resolved_location_type == "district":
                table_name = "district_assessments"
                filters["district"] = resolved_location
                if resolved_year:
                    filters["year"] = resolved_year
            elif resolved_location_type == "firka":
                table_name = "firka_assessments"
                select_fields = ["id", "district", "firka", "year", "total_recharge", "annual_extractable", "total_extraction", "stage_of_extraction", "category"]
                filters["firka"] = resolved_location
                if resolved_year:
                    filters["year"] = resolved_year
            elif resolved_location_type == "taluk":
                # Join firka_assessments with firka_master to filter by taluk
                table_name = "firka_assessments"
                select_fields = [
                    "firka_assessments.id", "firka_assessments.district", "firka_assessments.firka",
                    "firka_assessments.year", "firka_assessments.total_recharge", "firka_assessments.annual_extractable",
                    "firka_assessments.total_extraction", "firka_assessments.stage_of_extraction", "firka_assessments.category"
                ]
                joins = [{
                    "table": "firka_master",
                    "on": "firka_assessments.firka = firka_master.firka_name",
                    "type": "INNER"
                }]
                filters["firka_master.taluk_name"] = resolved_location
                if resolved_year:
                    filters["firka_assessments.year"] = resolved_year
            elif resolved_location_type == "village":
                table_name = "monitoring_data"
                select_fields = ["id", "station", "district", "village", "parameter", "acquisition_time", "value", "unit"]
                filters["station"] = resolved_location
                order_by = "acquisition_time ASC"
            elif resolved_location_type == "aquifer":
                table_name = "monitoring_data"
                select_fields = ["id", "station", "district", "village", "parameter", "acquisition_time", "value", "unit"]
                # Join monitoring well with aquifer master
                joins = [{
                    "table": "village_master",
                    "on": "monitoring_data.station = village_master.village_name",
                    "type": "INNER"
                }]
                filters["village_master.source"] = resolved_location # aquifer mapping
                order_by = "acquisition_time ASC"
            else:
                # Default safety district mapping
                table_name = "district_assessments"
                filters["district"] = resolved_location
                
            # Handle special ranking intent
            if "top" in query.lower() or "ranking" in query.lower():
                order_by = "stage_of_extraction DESC"
                # If doing general ranking, remove location filter
                if "district" in query.lower():
                    filters.pop("district", None)
                    filters.pop("firka", None)
                    
            # 4. Build dynamic SQL
            sql_str, sql_params = QueryBuilder.build(
                table_name=table_name,
                select_fields=select_fields,
                filters=filters,
                joins=joins,
                group_by=group_by,
                order_by=order_by
            )
            
            build_time = (time.time() - start_build) * 1000.0
            
            # 5. Execute SQLite query
            res = db.execute(text(sql_str), sql_params).fetchall()
            
            # Convert result rows to dictionary list
            records = []
            for row in res:
                # Select fields keys stripping aliases
                row_dict = {}
                for idx, field in enumerate(select_fields):
                    # handle qualified names like 'firka_assessments.id' -> 'id'
                    clean_key = field.split(".")[-1].split(" as ")[-1]
                    row_dict[clean_key] = row[idx]
                records.append(row_dict)
                
            # 6. Calculate statistics
            stats = {}
            if records:
                numeric_field = "stage_of_extraction" if "stage_of_extraction" in select_fields[3:] or "stage_of_extraction" in select_fields[0] else "value"
                if table_name == "monitoring_data":
                    numeric_field = "value"
                stats = StatisticsEngine.calculate_basic_stats(records, numeric_field)
                
            # 7. Generate visualizations
            chart_paths = []
            if len(records) >= 2 and ("chart" in response_type or "chart" in query.lower() or "trend" in query.lower()):
                x_f = "year" if table_name != "monitoring_data" else "acquisition_time"
                y_f = "stage_of_extraction" if table_name != "monitoring_data" else "value"
                chart_paths = ChartBuilder.generate_line_chart(
                    records=records,
                    x_field=x_f,
                    y_field=y_f,
                    title=f"{resolved_location.title()} {y_f.replace('_', ' ').title()} History",
                    session_id=session_id
                )
                
            # 8. Generate tables formatting
            markdown_table = ""
            if records:
                cols_mapping = DataAgent.COLUMNS_MAP.get(table_name, {})
                markdown_table = TableFormatter.format_markdown_table(records[:15], cols_mapping) # Limit to 15 rows for display
                
            # 9. Citations
            citations = DataCitations.compile_citations(table_name, records, resolved_year)
            
            # 10. Confidence
            conf = DataConfidence.calculate(
                resolved_location_type=resolved_location_type,
                is_exact_location=is_exact,
                sql_built_successfully=True,
                records=records,
                year=resolved_year
            )
            
            # 11. Compile Telemetry
            telemetry = DataMetrics.stop_tracking(db, sql_str, sql_params, metrics_tracker, len(records))
            telemetry["sql_build_time_ms"] = build_time
            
            db.close()
            
            # Formulate structured text response prefix
            answer = f"### Structured Data Results for {resolved_location.title()} ({resolved_location_type.upper()})\n\n"
            if resolved_year:
                answer += f"Assessment Year: **{resolved_year}**\n\n"
            if stats.get("count", 0) > 0:
                answer += (
                    f"- Record Count: **{stats['count']}**\n"
                    f"- Average Value: **{stats['mean']:.2f}**\n"
                    f"- Maximum Value: **{stats['max']:.2f}**\n"
                    f"- Minimum Value: **{stats['min']:.2f}**\n\n"
                )
            answer += markdown_table
            
            history = list(state.get("routing_history", []))
            history.append("data")
            
            return {
                "context_data": records,
                "chart_paths": chart_paths,
                "citations": citations,
                "confidence_score": conf["confidence_score"],
                "confidence_reason": f"Data retrieved from SQLite table {table_name}. Confidence level high.",
                "response": answer,
                "routing_history": history,
                "current_node": "synthesize"
            }
            
        except Exception as query_err:
            logger.error(f"DataAgent execution error: {query_err}", exc_info=True)
            if db:
                db.close()
            metrics = DataMetrics.stop_tracking(None, None, {}, metrics_tracker, 0)
            return {
                "context_data": [],
                "confidence_score": 0.20,
                "confidence_reason": f"Query execution failed: {query_err}",
                "response": f"❌ **DataAgent failed during SQL compile:** {str(query_err)}"
            }
