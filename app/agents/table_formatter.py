from typing import List, Dict, Any

class TableFormatter:
    """Formats raw structured database records into clean, user-friendly Markdown tables."""

    @classmethod
    def format_markdown_table(cls, records: List[Dict[str, Any]], columns_mapping: Dict[str, str]) -> str:
        """Translates field list into standard Markdown tables with custom headers mapping.
        
        Args:
            records: List of record dictionaries.
            columns_mapping: Dict mapping raw column name -> User facing header label.
                             e.g. {'district': 'District', 'total_recharge': 'Recharge (ham)'}
        """
        if not records:
            return "*No data records found to display.*"
            
        headers = list(columns_mapping.values())
        raw_cols = list(columns_mapping.keys())
        
        # Build headers
        header_row = "| " + " | ".join(headers) + " |"
        sep_row = "| " + " | ".join(["---"] * len(headers)) + " |"
        
        rows = []
        for r in records:
            row_vals = []
            for col in raw_cols:
                val = r.get(col)
                if val is None:
                    row_vals.append("-")
                elif isinstance(val, float):
                    row_vals.append(f"{val:.2f}")
                else:
                    row_vals.append(str(val))
            rows.append("| " + " | ".join(row_vals) + " |")
            
        return "\n".join([header_row, sep_row] + rows)

    @classmethod
    def format_pivot_table(
        cls, 
        records: List[Dict[str, Any]], 
        row_field: str, 
        col_field: str, 
        val_field: str
    ) -> str:
        """Compiles standard row-column pivot summaries for structured analytics."""
        if not records:
            return "*No data available for pivot.*"
            
        rows_labels = sorted(list(set(str(r[row_field]) for r in records if r.get(row_field) is not None)))
        cols_labels = sorted(list(set(str(r[col_field]) for r in records if r.get(col_field) is not None)))
        
        # Grid representation
        grid = {r: {c: "-" for c in cols_labels} for r in rows_labels}
        
        for r in records:
            rf = str(r.get(row_field))
            cf = str(r.get(col_field))
            vf = r.get(val_field)
            if rf in grid and cf in grid[rf] and vf is not None:
                grid[rf][cf] = f"{float(vf):.2f}" if isinstance(vf, float) else str(vf)
                
        # Format markdown
        header_row = f"| {row_field.title()} / {col_field.title()} | " + " | ".join(cols_labels) + " |"
        sep_row = "| " + " | ".join(["---"] * (len(cols_labels) + 1)) + " |"
        
        rows = []
        for r_label in rows_labels:
            row_vals = [r_label]
            for c_label in cols_labels:
                row_vals.append(grid[r_label][c_label])
            rows.append("| " + " | ".join(row_vals) + " |")
            
        return "\n".join([header_row, sep_row] + rows)
