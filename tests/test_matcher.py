import pytest
from app.intelligence.stair_matcher import StairMatcher

def test_stair_matcher_matches_backend_role():
    matcher = StairMatcher()
    title = "Backend Engineer - Python & FastAPI"
    company = "ScaleAI"
    location = "Remote India"
    description = "We are seeking a Backend Engineer with 2-4 years of experience in Python, FastAPI, PostgreSQL, Redis, and Celery."
    
    res = matcher.evaluate_match(title, company, location, description)
    assert res["score"] >= 70.0
    assert "python" in res["matched_skills"]
    assert "fastapi" in res["matched_skills"]
    assert res["tier"] == "P1"
    assert res["recommendation"] == "Apply"

def test_stair_matcher_excludes_intern():
    matcher = StairMatcher()
    title = "Software Engineer Intern"
    company = "TechCorp"
    location = "Hyderabad"
    description = "Summer internship for fresh graduates."
    
    res = matcher.evaluate_match(title, company, location, description)
    assert res["tier"] == "Excluded"
    assert res["recommendation"] == "Skip"
