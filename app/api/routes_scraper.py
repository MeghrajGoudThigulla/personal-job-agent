import json
from fastapi import APIRouter, BackgroundTasks, Query
from app.config import settings
from app.scrapers.engine import ScraperEngine

router = APIRouter(prefix="/api/scraper", tags=["Scraper Control"])
engine = ScraperEngine()

@router.post("/trigger")
async def trigger_scraper(background_tasks: BackgroundTasks, filter_type: str = Query("all", pattern="^(all|ats|remote|dorks)$")):
    """Triggers job discovery cycle in the background."""
    background_tasks.add_task(engine.run_discovery_cycle, filter_type)
    return {
        "status": "triggered",
        "filter": filter_type,
        "message": f"Job discovery initiated with filter '{filter_type}'. Alerts will dispatch automatically for >=70% matches."
    }

@router.get("/queries")
async def get_personalized_queries():
    """Returns the 121 tailored queries for all 11 roles."""
    if settings.PERSONALIZED_QUERIES_JSON.exists():
        with open(settings.PERSONALIZED_QUERIES_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"roles": []}
