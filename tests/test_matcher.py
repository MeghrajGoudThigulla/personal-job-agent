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

def test_stair_matcher_excludes_experience_higher_than_3_years():
    matcher = StairMatcher()
    # 4+ years (Apple style)
    res_apple = matcher.evaluate_match("Full Stack Engineer - Python", "Apple", "TS, India", "Requires 4+ years of experience in Python, React and PostgreSQL.")
    assert res_apple["score"] <= 20.0
    assert "Excluded" in res_apple["tier"]
    assert "Experience" in res_apple["tier"]

    # 3-5 years (Nike style)
    res_nike = matcher.evaluate_match("Software Engineer II", "Nike", "KA, India", "Requires 3-5 years of industry experience with Python and cloud services.")
    assert res_nike["score"] <= 20.0
    assert "Excluded" in res_nike["tier"]

    # Minimum 4 years
    res_min4 = matcher.evaluate_match("Python Developer", "TechCorp", "MH, India", "Candidate must have minimum 4 years of experience in FastAPI and Docker.")
    assert res_min4["score"] <= 20.0
    assert "Excluded" in res_min4["tier"]

def test_stair_matcher_3_yoe_accepted_only_if_strong_match():
    matcher = StairMatcher()
    # Strong match with 3 years (Python, FastAPI, React, PostgreSQL)
    res_strong = matcher.evaluate_match("Backend Engineer", "Groww", "Bengaluru", "Seeking engineer with 3 years of experience in Python, FastAPI, React, and PostgreSQL.")
    assert res_strong["score"] >= 70.0
    assert res_strong["recommendation"] == "Apply"

    # Weak match with 3 years (Only Python, weak preliminary score)
    res_weak = matcher.evaluate_match("Backend Engineer", "Groww", "Bengaluru", "Seeking engineer with 3 years of experience in Python.")
    assert res_weak["score"] <= 20.0
    assert "Excluded" in res_weak["tier"]

def test_stair_matcher_accepts_pan_india_cities_and_state_codes():
    matcher = StairMatcher()
    cities = [
        ("Nagpur, MH", "Python, FastAPI, PostgreSQL, 1-2 years experience"),
        ("Visakhapatnam, AP", "Python, React, TypeScript, 0-2 years"),
        ("Mohali, Punjab", "Python, FastAPI, PostgreSQL, 1 year experience"),
        ("Surat, Gujarat", "Python, Flask, Docker, 2 years experience"),
        ("Dehradun, Uttarakhand", "React, TypeScript, FastAPI, 1-2 years"),
        ("Kochi, Kerala", "Python, FastAPI, PostgreSQL, 0-2 years"),
        ("TS, India", "Python, FastAPI, Docker, 1-2 years experience"),
        ("KA, India", "Python, React, TypeScript, 1-2 years experience")
    ]
    for loc, desc in cities:
        res = matcher.evaluate_match("Software Engineer", "NationalTech", loc, desc)
        assert res["score"] >= 70.0, f"Failed for location {loc}: score={res['score']}, tier={res['tier']}"
        assert res["recommendation"] == "Apply"

def test_stair_matcher_accepts_primary_band_0_to_2_years_3_months():
    matcher = StairMatcher()
    res_0_2 = matcher.evaluate_match("Junior Backend Developer", "Fintech", "Hyderabad, India", "Requires 0 to 2 years of experience in Python and FastAPI.")
    assert res_0_2["score"] >= 70.0
    assert res_0_2["recommendation"] == "Apply"

    res_1_2 = matcher.evaluate_match("Associate Software Engineer", "SaaS Co", "Pune", "1-2 years experience with Python, FastAPI, and PostgreSQL.")
    assert res_1_2["score"] >= 75.0
    assert res_1_2["recommendation"] == "Apply"
