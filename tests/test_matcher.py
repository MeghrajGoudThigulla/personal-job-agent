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
    assert res["location_category"] == "Remote (India)"
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

def test_stair_matcher_accepts_india_onsite():
    matcher = StairMatcher()
    title = "Software Engineer II - Backend"
    company = "Razorpay"
    location = "Bengaluru, India"
    description = "We need an engineer with 2-4 years experience in Python, FastAPI, PostgreSQL and Redis."

    res = matcher.evaluate_match(title, company, location, description)
    assert res["score"] >= 70.0
    assert "India" in res["location_category"]
    assert res["recommendation"] == "Apply"

def test_stair_matcher_accepts_remote_worldwide():
    matcher = StairMatcher()
    title = "Product Engineer"
    company = "Linear"
    location = "Remote - Worldwide"
    description = "Building next generation developer tools with TypeScript, React, Node.js, PostgreSQL and Redis. Fully distributed global team."

    res = matcher.evaluate_match(title, company, location, description)
    assert res["score"] >= 70.0
    assert "Worldwide" in res["location_category"]
    assert res["recommendation"] == "Apply"

def test_stair_matcher_excludes_us_only_restriction():
    matcher = StairMatcher()
    title = "Senior Python Engineer"
    company = "USCorp"
    location = "Remote - US Only"
    description = "Must reside in the US. US citizenship required. Python, FastAPI, Docker."

    res = matcher.evaluate_match(title, company, location, description)
    assert res["score"] <= 20.0
    assert "Excluded" in res["tier"]
    assert res["recommendation"] == "Skip"

def test_stair_matcher_excludes_non_india_onsite():
    matcher = StairMatcher()
    title = "Backend Engineer"
    company = "LondonFintech"
    location = "London, UK"
    description = "Onsite role at our central London office. Python, PostgreSQL, Redis, 2-4 years experience."

    res = matcher.evaluate_match(title, company, location, description)
    assert res["score"] <= 20.0
    assert "Excluded" in res["tier"]
    assert res["recommendation"] == "Skip"

def test_stair_matcher_excludes_emea_and_amer_in_title():
    matcher = StairMatcher()
    res_emea = matcher.evaluate_match("Support Engineer (EMEA)", "Supabase", "Remote", "PostgreSQL, Python, Redis")
    assert res_emea["score"] <= 20.0
    assert "Excluded" in res_emea["tier"]

    res_amer = matcher.evaluate_match("Support Engineer (AMER)", "Supabase", "Remote", "PostgreSQL, Python, Redis")
    assert res_amer["score"] <= 20.0
    assert "Excluded" in res_amer["tier"]

def test_stair_matcher_accepts_apac_in_title():
    matcher = StairMatcher()
    res_apac = matcher.evaluate_match("Support Engineer (APAC)", "Supabase", "Remote", "PostgreSQL, Python, Redis, 2-4 years experience")
    assert res_apac["score"] >= 70.0
    assert "APAC" in res_apac["location_category"]

def test_stair_matcher_excludes_europe_location():
    matcher = StairMatcher()
    res_euro = matcher.evaluate_match("Senior / Staff Fullstack Engineer", "Linear", "Europe", "TypeScript, React, PostgreSQL")
    assert res_euro["score"] <= 20.0
    assert "Excluded" in res_euro["tier"]
