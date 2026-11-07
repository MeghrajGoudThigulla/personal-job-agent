from datetime import datetime, timezone

from app.intelligence.stair_matcher import StairMatcher


def test_candidate_years_progression():
    matcher = StairMatcher()

    d_2025 = datetime(2025, 7, 1, tzinfo=timezone.utc)
    assert matcher.candidate_years(today=d_2025) == 1.0

    d_2026 = datetime(2026, 7, 1, tzinfo=timezone.utc)
    assert matcher.candidate_years(today=d_2026) == 2.0

    d_oct_2026 = datetime(2026, 10, 15, tzinfo=timezone.utc)
    assert matcher.candidate_years(today=d_oct_2026) == 2.3

    d_2027 = datetime(2027, 7, 1, tzinfo=timezone.utc)
    assert matcher.candidate_years(today=d_2027) == 3.0


def test_parse_experience_range_robustness():
    matcher = StairMatcher()

    # Range
    assert matcher.parse_experience_range("2-4 years") == (2.0, 4.0)
    assert matcher.parse_experience_range("1 to 3 years of experience") == (1.0, 3.0)
    assert matcher.parse_experience_range("2 - 4 yrs of industry experience") == (2.0, 4.0)
    assert matcher.parse_experience_range("1-3 yoe") == (1.0, 3.0)

    # Plus / minimum
    assert matcher.parse_experience_range("3+ years") == (3.0, None)
    assert matcher.parse_experience_range("3+ yrs") == (3.0, None)
    assert matcher.parse_experience_range("minimum 2 years") == (2.0, None)
    assert matcher.parse_experience_range("at least 3 years of experience") == (3.0, None)

    # Exact / Single number
    assert matcher.parse_experience_range("5 years of experience") == (5.0, 5.0)
    assert matcher.parse_experience_range("requires 5 years") == (5.0, 5.0)

    # None when no experience stated
    assert matcher.parse_experience_range("FastAPI, Python, SQL backend developer.") is None
    assert matcher.parse_experience_range("") is None
    assert matcher.parse_experience_range(None) is None


def test_experience_behavior_against_candidate_with_2_point_3_years():
    matcher = StairMatcher()
    # Candidate with 2.3 YOE on 2026-10-15
    today_2_3 = datetime(2026, 10, 15, tzinfo=timezone.utc)
    assert matcher.candidate_years(today_2_3) == 2.3

    # Common job details
    title = "Python Engineer"
    company = "TechCo"
    location = "Hyderabad, India"

    # 1. Stated "2-4 years" -> stated min is 2.0 <= 2.3 + 1.0 -> Accepted!
    res_range = matcher.evaluate_match(
        title=title,
        company=company,
        location=location,
        description="We are looking for a Python engineer with 2-4 years of experience building FastAPI microservices.",
        today=today_2_3,
    )
    assert res_range["score"] >= 70.0
    assert "Excluded (Experience)" not in res_range["tier"]

    # 2. Stated "3+ years" -> stated min is 3.0 <= 2.3 + 1.0 (3.3) -> Accepted on strong match!
    res_plus = matcher.evaluate_match(
        title=title,
        company=company,
        location=location,
        description="Seeking a backend developer with 3+ years of experience in Python, FastAPI, and PostgreSQL.",
        today=today_2_3,
    )
    assert res_plus["score"] >= 70.0
    assert "Excluded (Experience)" not in res_plus["tier"]

    # 3. Stated "5 years" -> stated min is 5.0 > 4.3 -> strictly Rejected!
    res_five = matcher.evaluate_match(
        title=title,
        company=company,
        location=location,
        description="Requires 5 years of experience in Python and distributed systems.",
        today=today_2_3,
    )
    assert res_five["score"] == 15.0
    assert res_five["tier"] == "Excluded (Experience)"
    assert "exceeds candidate ceiling" in res_five["verdict"]

    # 4. No experience stated -> No penalty!
    res_no_exp = matcher.evaluate_match(
        title=title,
        company=company,
        location=location,
        description="Python, FastAPI, Postgres, Docker engineer.",
        today=today_2_3,
    )
    assert res_no_exp["score"] >= 70.0
    assert "Excluded (Experience)" not in res_no_exp["tier"]


def test_title_blocklist_allows_senior_when_candidate_years_crosses_three():
    matcher = StairMatcher()

    title = "Senior Python Engineer"
    desc = "Python, FastAPI, PostgreSQL, Docker developer in Hyderabad, India."

    # When candidate has 2.3 YOE (< 3.0), 'Senior' is blocked
    today_2_3 = datetime(2026, 10, 15, tzinfo=timezone.utc)
    res_junior = matcher.evaluate_match(
        title=title,
        company="TechCo",
        location="Hyderabad, India",
        description=desc,
        today=today_2_3,
    )
    assert res_junior["score"] == 15.0
    assert res_junior["tier"] == "Excluded"
    assert "title level/role disqualifier" in res_junior["verdict"]

    # When candidate has 3.3 YOE (>= 3.0) on 2027-10-15, 'Senior' is allowed!
    today_3_3 = datetime(2027, 10, 15, tzinfo=timezone.utc)
    assert matcher.candidate_years(today_3_3) >= 3.0
    res_senior = matcher.evaluate_match(
        title=title,
        company="TechCo",
        location="Hyderabad, India",
        description=desc,
        today=today_3_3,
    )
    assert res_senior["score"] >= 70.0
    assert res_senior["tier"] != "Excluded"


def test_profile_driven_skills_and_weights(caplog):
    matcher = StairMatcher()
    assert matcher.weight_primary == 10.0
    assert matcher.weight_specialized == 4.5
    assert matcher.weight_generic == 1.5
    assert "python" in matcher.primary_skills
    assert "postgresql" in matcher.specialized_skills
    assert "sql" in matcher.generic_skills

    # Test fallback with missing keys
    empty_matcher = StairMatcher.__new__(StairMatcher)
    empty_matcher.profile = {}
    with caplog.at_level("WARNING", logger="personal_job_agent.stair_matcher"):
        empty_matcher._setup_profile_skills_and_weights()
    assert "Profile missing skills.primary" in caplog.text
    assert empty_matcher.primary_skills == StairMatcher.PRIMARY_CORE_SKILLS
