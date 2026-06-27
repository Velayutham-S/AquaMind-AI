import os
import time
import matplotlib
matplotlib.use('Agg') # Thread-safe non-GUI backend
import matplotlib.pyplot as plt
from datetime import datetime
from typing import List, Dict, Any
from app.config import Config
from app.logging_config import logger

class ChartBuilder:
    """Thread-safe matplotlib chart generation service saving visualizations to reports/charts."""

    @classmethod
    def generate_line_chart(
        cls, 
        records: List[Dict[str, Any]], 
        x_field: str, 
        y_field: str, 
        title: str, 
        session_id: str = "default"
    ) -> List[str]:
        """Generates a line plot showing trends over time."""
        if len(records) < 2:
            return []
            
        # Sort chronologically by x_field (usually year)
        sorted_recs = sorted(records, key=lambda x: str(x.get(x_field, "")))
        x_data = [str(r.get(x_field)) for r in sorted_recs]
        y_data = [float(r.get(y_field)) for r in sorted_recs if r.get(y_field) is not None]
        
        if len(x_data) != len(y_data) or not y_data:
            return []
            
        plt.figure(figsize=(8, 4))
        plt.plot(x_data, y_data, marker='o', color='royalblue', linewidth=2, label=y_field.replace('_', ' ').title())
        plt.title(title, fontsize=12, fontweight='bold')
        plt.xlabel(x_field.replace('_', ' ').title())
        plt.ylabel("Value")
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.legend()
        plt.tight_layout()
        
        return cls._save_fig(session_id)

    @classmethod
    def generate_comparison_bar_chart(
        cls, 
        records: List[Dict[str, Any]], 
        label_field: str, 
        value_fields: List[str], 
        title: str, 
        session_id: str = "default"
    ) -> List[str]:
        """Generates a grouped or single bar chart comparing multiple fields or items."""
        if not records or not value_fields:
            return []
            
        labels = [str(r.get(label_field))[:15] for r in records] # Limit text length
        
        plt.figure(figsize=(9, 4.5))
        
        x = range(len(labels))
        width = 0.35
        
        for idx, field in enumerate(value_fields):
            y_data = [float(r.get(field, 0.0) or 0.0) for r in records]
            offset = (idx - len(value_fields)/2) * width + width/2
            plt.bar([pos + offset for pos in x], y_data, width, label=field.replace('_', ' ').title())
            
        plt.xticks(x, labels, rotation=45, ha='right')
        plt.title(title, fontsize=12, fontweight='bold')
        plt.grid(True, linestyle=':', alpha=0.5, axis='y')
        plt.legend()
        plt.tight_layout()
        
        return cls._save_fig(session_id)

    @classmethod
    def generate_pie_chart(
        cls, 
        slices_dict: Dict[str, float], 
        title: str, 
        session_id: str = "default"
    ) -> List[str]:
        """Generates a pie chart displaying proportion breakdowns (e.g. extraction domains)."""
        labels = list(slices_dict.keys())
        values = list(slices_dict.values())
        
        if not values or sum(values) == 0.0:
            return []
            
        plt.figure(figsize=(6, 5))
        colors = ['#ff9999','#66b3ff','#99ff99','#ffcc99']
        plt.pie(values, labels=labels, autopct='%1.1f%%', startangle=140, colors=colors[:len(labels)])
        plt.title(title, fontsize=12, fontweight='bold')
        plt.tight_layout()
        
        return cls._save_fig(session_id)

    @classmethod
    def generate_scatter_plot(
        cls, 
        records: List[Dict[str, Any]], 
        x_field: str, 
        y_field: str, 
        title: str, 
        session_id: str = "default"
    ) -> List[str]:
        """Generates a scatter plot comparing two numerical variables."""
        x_data = [float(r[x_field]) for r in records if r.get(x_field) is not None]
        y_data = [float(r[y_field]) for r in records if r.get(y_field) is not None]
        
        if not x_data or not y_data:
            return []
            
        plt.figure(figsize=(7, 4.5))
        plt.scatter(x_data, y_data, color='forestgreen', alpha=0.7, edgecolors='black')
        plt.title(title, fontsize=12, fontweight='bold')
        plt.xlabel(x_field.replace('_', ' ').title())
        plt.ylabel(y_field.replace('_', ' ').title())
        plt.grid(True, linestyle='--', alpha=0.5)
        plt.tight_layout()
        
        return cls._save_fig(session_id)

    @classmethod
    def _save_fig(cls, session_id: str) -> List[str]:
        chart_dir = Config.BASE_DIR / "reports" / "charts"
        chart_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"chart_{session_id}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.png"
        filepath = chart_dir / filename
        
        try:
            plt.savefig(filepath, dpi=100)
            plt.close()
            logger.info(f"Visualized chart exported to {filepath}")
            return [str(filepath)]
        except Exception as e:
            logger.error(f"Failed to export visualization: {e}")
            plt.close()
            return []
