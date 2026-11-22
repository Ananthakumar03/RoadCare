import pandas as pd

def prepare_complaints(rows):
    """Convert database rows into a DataFrame for analytics."""
    columns = [
        "id", "title", "area", "damage_type", "severity",
        "traffic_level", "accident_count", "status", "created_at"
    ]
    df = pd.DataFrame(rows, columns=columns)
    if df.empty:
        return df
    for col in ["severity", "traffic_level", "accident_count"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df

def calculate_priority(row, repeated_reports=1):
    """
    Transparent decision-support score (0–100).
    Severity 40%, traffic 25%, accident reports 20%, repeated reports 15%.
    These are prototype weights and should be reviewed with domain experts.
    """
    severity = max(1, min(5, int(row["severity"]))) / 5
    traffic = max(1, min(5, int(row["traffic_level"]))) / 5
    accidents = min(max(0, int(row["accident_count"])), 5) / 5
    repeats = min(max(1, int(repeated_reports)), 5) / 5
    score = (severity * 40) + (traffic * 25) + (accidents * 20) + (repeats * 15)
    return round(score, 1)

def priority_label(score):
    if score >= 75:
        return "High"
    if score >= 50:
        return "Medium"
    return "Low"
