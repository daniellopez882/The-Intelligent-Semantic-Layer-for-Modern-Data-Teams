import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional, Any

class ResultVisualizer:
    """Enterprise-grade automatic data visualization"""
    
    # Futuristic color palette
    COLORS = ['#00f2ff', '#7000ff', '#ff007a', '#00ffab', '#ffea00']
    
    @staticmethod
    def should_visualize(df: pd.DataFrame) -> bool:
        if df.empty or len(df) < 2:
            return False
        return len(df.select_dtypes(include=['number']).columns) > 0
    
    @staticmethod
    def auto_visualize(df: pd.DataFrame, title: str = "Analysis Results") -> Optional[Any]:
        if not ResultVisualizer.should_visualize(df):
            return None
        
        # Clean columns for display
        df.columns = [c.replace('_', ' ').title() for c in df.columns]
        
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
        # Detect date-like columns that might be objects
        date_cols = []
        for col in categorical_cols:
            if 'date' in col.lower() or 'time' in col.lower() or 'month' in col.lower():
                try:
                    df[col] = pd.to_datetime(df[col])
                    date_cols.append(col)
                except:
                    pass
        
        categorical_cols = [c for c in categorical_cols if c not in date_cols]

        # Chart choosing logic
        try:
            # 1. Timeline Chart
            if date_cols and numeric_cols:
                fig = px.line(df, x=date_cols[0], y=numeric_cols[0], title=title,
                             template="plotly_dark", color_discrete_sequence=ResultVisualizer.COLORS)
                fig.update_traces(line=dict(width=3, shape='spline'))
            
            # 2. Categorical vs Numeric (Bar/Pie)
            elif categorical_cols and numeric_cols:
                # If few categories, use Pie
                if len(df) <= 5 and len(numeric_cols) == 1:
                    fig = px.pie(df, names=categorical_cols[0], values=numeric_cols[0], title=title,
                                hole=0.4, template="plotly_dark", color_discrete_sequence=ResultVisualizer.COLORS)
                else:
                    fig = px.bar(df, x=categorical_cols[0], y=numeric_cols[0], title=title,
                                template="plotly_dark", color_discrete_sequence=ResultVisualizer.COLORS)
                    fig.update_traces(marker_line_color='rgba(255,255,255,0.2)', marker_line_width=1.5)
            
            # 3. Two Numeric (Scatter)
            elif len(numeric_cols) >= 2:
                fig = px.scatter(df, x=numeric_cols[0], y=numeric_cols[1], title=title,
                                template="plotly_dark", color_discrete_sequence=ResultVisualizer.COLORS,
                                size=numeric_cols[1] if len(numeric_cols) > 1 else None)
            
            # 4. Single Numeric (Metric Chart)
            else:
                fig = px.bar(df, y=numeric_cols[0], title=title,
                            template="plotly_dark", color_discrete_sequence=ResultVisualizer.COLORS)

            # High-end styling
            fig.update_layout(
                font_family="Inter",
                title_font_size=20,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False, zeroline=False),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', zeroline=False),
                margin=dict(l=40, r=40, t=60, b=40),
                hoverlabel=dict(bgcolor="#161821", font_size=14, font_family="Inter")
            )
            return fig
        except Exception as e:
            print(f"Viz Error: {e}")
            return None

    @staticmethod
    def get_summary_stats(df: pd.DataFrame) -> str:
        numeric_df = df.select_dtypes(include=['number'])
        if numeric_df.empty:
            return f"Dataset contains {len(df)} entries with no numerical metrics."
            
        summary = f"Summary Metrics ({len(df)} records):\n"
        for col in numeric_df.columns:
            clean_name = col.replace('_', ' ').title()
            val_sum = numeric_df[col].sum()
            val_avg = numeric_df[col].mean()
            
            if 'price' in col.lower() or 'amount' in col.lower() or 'total' in col.lower():
                summary += f"• {clean_name}: Total value is ${val_sum:,.2f} (Avg: ${val_avg:,.2f})\n"
            else:
                summary += f"• {clean_name}: Sum {val_sum:,.0f} (Avg: {val_avg:,.1f})\n"
        return summary
