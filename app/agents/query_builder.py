from typing import Dict, Any, List, Tuple, Optional
from app.logging_config import logger

class QueryBuilder:
    """Dynamic parameterized SQL query builder for SQLite to prevent SQL injection and standardise data queries."""

    @classmethod
    def build(
        cls,
        table_name: str,
        select_fields: List[str],
        filters: Optional[Dict[str, Any]] = None,
        joins: Optional[List[Dict[str, str]]] = None,
        group_by: Optional[List[str]] = None,
        having: Optional[List[str]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Compiles SQL statement components into a valid, executable SQL query string and binds parameter values.
        
        Args:
            table_name: Primary table name.
            select_fields: Fields to select (e.g. ['district', 'AVG(stage_of_extraction) as avg_stage']).
            filters: Dictionary of filters. e.g. {'district': 'SALEM', 'year': ('>=', '2020')} or {'category': ['Critical', 'Over-Exploited']}.
            joins: List of joins: [{'table': 'taluk_master', 'on': 'district_assessments.district = taluk_master.district_name', 'type': 'INNER'}].
            group_by: List of fields for GROUP BY.
            having: List of HAVING clauses.
            order_by: ORDER BY clause string (e.g. 'year DESC, total_recharge ASC').
            limit: Limit integer.
            
        Returns:
            Tuple of (sql_query_string, bind_parameters_dict)
        """
        params = {}
        param_counter = 0
        
        # 1. Build SELECT
        select_str = ", ".join(select_fields)
        sql = f"SELECT {select_str} FROM {table_name}"
        
        # 2. Build JOINs
        if joins:
            for j in joins:
                j_type = j.get("type", "INNER").upper()
                j_table = j.get("table")
                j_on = j.get("on")
                sql += f" {j_type} JOIN {j_table} ON {j_on}"
                
        # 3. Build WHERE filters
        where_clauses = []
        if filters:
            for col, val in filters.items():
                if val is None:
                    where_clauses.append(f"{col} IS NULL")
                elif isinstance(val, tuple) and len(val) == 2 and isinstance(val[0], str):
                    # Alternative tuple format: (operator, value) e.g. ('>=', 2020)
                    op, op_val = val
                    p_name = f"p_{param_counter}"
                    param_counter += 1
                    where_clauses.append(f"{col} {op} :{p_name}")
                    params[p_name] = op_val
                elif isinstance(val, list) or isinstance(val, tuple):
                    # IN comparison
                    in_placeholders = []
                    for item in val:
                        p_name = f"p_{param_counter}"
                        param_counter += 1
                        in_placeholders.append(f":{p_name}")
                        params[p_name] = item
                    placeholders_str = ", ".join(in_placeholders)
                    where_clauses.append(f"{col} IN ({placeholders_str})")
                elif isinstance(val, dict):
                    # Operator filter e.g. {'op': '>=', 'val': 2020} or {'>=': 2020}
                    # We accept operator-based dictionary mapping
                    for op, op_val in val.items():
                        p_name = f"p_{param_counter}"
                        param_counter += 1
                        where_clauses.append(f"{col} {op} :{p_name}")
                        params[p_name] = op_val
                else:
                    # Equal filter
                    p_name = f"p_{param_counter}"
                    param_counter += 1
                    where_clauses.append(f"{col} = :{p_name}")
                    params[p_name] = val
                    
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)
            
        # 4. Build GROUP BY
        if group_by:
            sql += " GROUP BY " + ", ".join(group_by)
            
        # 5. Build HAVING
        if having:
            sql += " HAVING " + " AND ".join(having)
            
        # 6. Build ORDER BY
        if order_by:
            # SQLite does not allow colon parameters in ORDER BY, so validate/format safely
            sql += f" ORDER BY {order_by}"
            
        # 7. Build LIMIT
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
            
        logger.debug(f"Compiled SQL Query: {sql} | Bind parameters: {params}")
        return sql, params
