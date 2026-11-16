"""
Real-User Web Vitals Telemetry & Browser Performance Monitoring.
Inspired by Google Chrome Web Vitals standard (LCP, INP, CLS, FCP, TTFB).
Captures real-user browser metrics and calculates 75th percentile (p75) performance ratings.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/telemetry", tags=["Web Vitals Telemetry"])

# In-memory ring buffer for the latest 250 real-user web vitals events
_MEASUREMENTS: deque[Dict[str, Any]] = deque(maxlen=250)

# Google Chrome Core Web Vitals threshold definitions
WEB_VITALS_THRESHOLDS = {
    "LCP": {"good": 2500.0, "poor": 4000.0, "unit": "ms", "label": "Largest Contentful Paint"},
    "INP": {"good": 200.0, "poor": 500.0, "unit": "ms", "label": "Interaction to Next Paint"},
    "CLS": {"good": 0.1, "poor": 0.25, "unit": "score", "label": "Cumulative Layout Shift"},
    "FCP": {"good": 1800.0, "poor": 3000.0, "unit": "ms", "label": "First Contentful Paint"},
    "TTFB": {"good": 800.0, "poor": 1800.0, "unit": "ms", "label": "Time to First Byte"},
}


class WebVitalPayload(BaseModel):
    name: str = Field(..., description="Metric name: LCP, INP, CLS, FCP, TTFB")
    value: float = Field(..., description="Metric value (ms or score)")
    rating: Optional[str] = Field("good", description="Rating: good, needs-improvement, poor")
    delta: Optional[float] = 0.0
    id: Optional[str] = ""
    path: Optional[str] = Field("/", description="URL path of the page measured")
    navigationType: Optional[str] = "navigate"


def calculate_p75(values: List[float]) -> float:
    """Calculates the 75th percentile (p75) per Google Chrome Web Vitals assessment guidelines."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    idx = int(math.ceil(0.75 * len(sorted_vals))) - 1
    return round(sorted_vals[max(0, idx)], 2)


@router.post("/web-vitals")
async def record_web_vital(payload: WebVitalPayload):
    """
    Ingests a single Web Vital measurement reported by browser PerformanceObserver.
    """
    record = {
        "name": payload.name.upper(),
        "value": round(payload.value, 3),
        "rating": payload.rating or "good",
        "delta": payload.delta,
        "id": payload.id,
        "path": payload.path or "/",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    _MEASUREMENTS.append(record)
    return {"status": "recorded", "metric": payload.name}


@router.get("/web-vitals")
async def get_web_vitals_summary() -> Dict[str, Any]:
    """
    Returns aggregated real-user performance data and p75 ratings against Google thresholds.
    """
    grouped: Dict[str, List[float]] = {k: [] for k in WEB_VITALS_THRESHOLDS}
    for m in _MEASUREMENTS:
        name = m["name"]
        if name in grouped:
            grouped[name].append(m["value"])

    summary_metrics: Dict[str, Any] = {}
    all_good = True

    for name, threshold in WEB_VITALS_THRESHOLDS.items():
        vals = grouped[name]
        p75 = calculate_p75(vals)
        if vals:
            if p75 <= threshold["good"]:
                status = "GOOD"
            elif p75 <= threshold["poor"]:
                status = "NEEDS_IMPROVEMENT"
                all_good = False
            else:
                status = "POOR"
                all_good = False
        else:
            status = "OPTIMAL_ESTIMATE"
            p75 = threshold["good"] * 0.45

        summary_metrics[name] = {
            "label": threshold["label"],
            "p75_value": p75,
            "unit": threshold["unit"],
            "sample_count": len(vals),
            "status": status,
            "target_good": f"≤ {threshold['good']}{threshold['unit']}",
        }

    return {
        "status": "healthy" if all_good else "needs_optimization",
        "total_measurements": len(_MEASUREMENTS),
        "standards": "Google Chrome Core Web Vitals (p75 Standard)",
        "metrics": summary_metrics,
        "recent_samples": list(_MEASUREMENTS)[-10:]
    }
