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

def test_stair_matcher_excludes_generic_worldwide_remote():
    matcher = StairMatcher()
    title = "Product Engineer"
    company = "Linear"
    location = "Remote - Worldwide"
    description = "Building next generation developer tools with TypeScript, React, Node.js, PostgreSQL and Redis. Fully distributed global team."

    res = matcher.evaluate_match(title, company, location, description)
    # Strictly India only: generic worldwide remote without India presence is excluded
    assert res["score"] <= 20.0
    assert "Excluded" in res["tier"]
    assert res["recommendation"] == "Skip"

def test_stair_matcher_excludes_senior_and_lead():
    matcher = StairMatcher()
    # Senior title
    res_sr = matcher.evaluate_match("Senior Software Engineer", "Swiggy", "Bengaluru", "Python, FastAPI, 2-4 years")
    assert res_sr["score"] <= 20.0
    assert "Excluded" in res_sr["tier"]

    # Tech Lead
    res_lead = matcher.evaluate_match("Tech Lead - Backend", "Zomato", "Gurgaon", "Python, PostgreSQL")
    assert res_lead["score"] <= 20.0
    assert "Excluded" in res_lead["tier"]

    # QA / SDET
    res_qa = matcher.evaluate_match("SDET II / QA Automation", "PhonePe", "Bengaluru", "Python, Selenium, PyTest")
    assert res_qa["score"] <= 20.0
    assert "Excluded" in res_qa["tier"]

def test_stair_matcher_excludes_heavy_yoe():
    matcher = StairMatcher()
    res = matcher.evaluate_match("Software Engineer", "Amazon", "Hyderabad", "Requires 7+ years of experience with Python and distributed systems.")
    assert res["score"] <= 20.0
    assert "Excluded" in res["tier"]
    assert "Experience" in res["tier"]

def test_stair_matcher_excludes_java_spring_stack():
    matcher = StairMatcher()
    # Java title
    res_java = matcher.evaluate_match("Java Backend Developer", "Infosys", "Hyderabad", "Java 17, Spring Boot, Microservices, PostgreSQL, Docker")
    assert res_java["score"] <= 20.0
    assert "Excluded" in res_java["tier"]

    # No core resume tech (only generic tools like sql, docker, git)
    res_generic = matcher.evaluate_match("Software Engineer", "TCS", "Pune", "SQL, Docker, Git, Linux, Jira, Agile")
    assert res_generic["score"] <= 20.0
    assert "Excluded" in res_generic["tier"]

def test_stair_matcher_accepts_india_remote_and_onsite():
    matcher = StairMatcher()
    # Hyderabad onsite
    res_hyd = matcher.evaluate_match("Backend Engineer (SDE II)", "HighTech", "Hyderabad, India", "Python, FastAPI, PostgreSQL, Docker, 2-3 years experience")
    assert res_hyd["score"] >= 70.0
    assert res_hyd["recommendation"] == "Apply"

    # Remote India
    res_rem = matcher.evaluate_match("Full Stack Engineer", "StartUp", "Remote, India", "React, TypeScript, FastAPI, PostgreSQL, 1-3 years")
    assert res_rem["score"] >= 70.0
    assert res_rem["recommendation"] == "Apply"
