import numpy as np
from typing import List, Dict, Any, Tuple

class StatisticsEngine:
    """Computes mathematical and statistical analytical summaries over retrieved records."""

    @classmethod
    def calculate_basic_stats(cls, records: List[Dict[str, Any]], field: str) -> Dict[str, Any]:
        """Calculates min, max, average, median, standard deviation, variance, and percentiles."""
        values = [float(r[field]) for r in records if r.get(field) is not None]
        
        if not values:
            return {
                "count": 0, "min": 0.0, "max": 0.0, "mean": 0.0, "median": 0.0,
                "std_dev": 0.0, "variance": 0.0, "percentiles": {25: 0.0, 50: 0.0, 75: 0.0, 90: 0.0}
            }
            
        arr = np.array(values)
        return {
            "count": len(values),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "mean": float(np.mean(arr)),
            "median": float(np.median(arr)),
            "std_dev": float(np.std(arr)),
            "variance": float(np.var(arr)),
            "percentiles": {
                25: float(np.percentile(arr, 25)),
                50: float(np.percentile(arr, 50)),
                75: float(np.percentile(arr, 75)),
                90: float(np.percentile(arr, 90))
            }
        }

    @classmethod
    def calculate_moving_average(cls, records: List[Dict[str, Any]], field: str, window: int = 3) -> List[Dict[str, Any]]:
        """Calculates rolling simple moving averages (SMA) for sequential records."""
        # Ensure ordered chronologically
        sorted_records = sorted(records, key=lambda x: str(x.get("year", "")))
        values = [r.get(field) for r in sorted_records]
        
        results = []
        for i, rec in enumerate(sorted_records):
            start = max(0, i - window + 1)
            subset = [float(v) for v in values[start:i+1] if v is not None]
            sma = float(np.mean(subset)) if subset else 0.0
            results.append({
                "year": rec.get("year"),
                "value": rec.get(field),
                "moving_avg": sma
            })
        return results

    @classmethod
    def calculate_yoy_growth(cls, records: List[Dict[str, Any]], field: str, year_field: str = "year") -> List[Dict[str, Any]]:
        """Calculates Year-over-Year percentage change growth across consecutive time records."""
        sorted_recs = sorted(records, key=lambda x: str(x.get(year_field, "")))
        
        results = []
        for i, rec in enumerate(sorted_recs):
            yoy_growth = 0.0
            if i > 0:
                prev_val = sorted_recs[i-1].get(field)
                curr_val = rec.get(field)
                if prev_val and curr_val and float(prev_val) != 0.0:
                    yoy_growth = ((float(curr_val) - float(prev_val)) / float(prev_val)) * 100.0
            results.append({
                "year": rec.get(year_field),
                "value": rec.get(field),
                "yoy_growth_pct": float(yoy_growth)
            })
        return results

    @classmethod
    def calculate_trend(cls, records: List[Dict[str, Any]], field: str, year_field: str = "year") -> Dict[str, Any]:
        """Calculates regression trend slope and direction (increasing, decreasing, or stable)."""
        sorted_recs = sorted(records, key=lambda x: str(x.get(year_field, "")))
        
        years = []
        values = []
        
        for r in sorted_recs:
            y_val = r.get(year_field)
            f_val = r.get(field)
            if y_val and f_val is not None:
                # Convert year range (e.g. "2024-2025" -> 2024) to numeric
                try:
                    start_yr = int(str(y_val).split("-")[0])
                    years.append(start_yr)
                    values.append(float(f_val))
                except Exception:
                    pass
                    
        if len(years) < 2:
            return {"direction": "insufficient_data", "slope": 0.0, "r_squared": 0.0}
            
        x = np.array(years)
        y = np.array(values)
        
        # Fit linear regression line: y = m*x + c
        A = np.vstack([x, np.ones(len(x))]).T
        m, c = np.linalg.lstsq(A, y, rcond=None)[0]
        
        # Calculate R-squared correlation value
        y_pred = m * x + c
        y_mean = np.mean(y)
        ss_tot = np.sum((y - y_mean) ** 2)
        ss_res = np.sum((y - y_pred) ** 2)
        r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 0 else 1.0
        
        # Classify trend direction
        # Threshold: if change is within 0.5% (relative/absolute or slope limits), mark stable
        # Let's use standard slope threshold (e.g., |slope| > 0.05)
        if m > 0.05:
            direction = "increasing"
        elif m < -0.05:
            direction = "decreasing"
        else:
            direction = "stable"
            
        return {
            "direction": direction,
            "slope": float(m),
            "r_squared": r2
        }

    @classmethod
    def calculate_rankings(
        cls, 
        records: List[Dict[str, Any]], 
        label_field: str, 
        score_field: str, 
        top_k: int = 10
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Extracts Top-K and Bottom-K item records sorted by score_field values."""
        valid_recs = [r for r in records if r.get(score_field) is not None]
        
        # Sort descending
        sorted_desc = sorted(valid_recs, key=lambda x: float(x[score_field]), reverse=True)
        
        top_list = []
        for rank, r in enumerate(sorted_desc[:top_k]):
            top_list.append({
                "rank": rank + 1,
                "label": r.get(label_field),
                "score": float(r[score_field]),
                "record": r
            })
            
        # Bottom-K list (reverse sort)
        sorted_asc = sorted(valid_recs, key=lambda x: float(x[score_field]))
        bottom_list = []
        for rank, r in enumerate(sorted_asc[:top_k]):
            bottom_list.append({
                "rank": rank + 1,
                "label": r.get(label_field),
                "score": float(r[score_field]),
                "record": r
            })
            
        return {
            "top_k": top_list,
            "bottom_k": bottom_list
        }
