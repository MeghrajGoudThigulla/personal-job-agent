from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, Optional, Tuple
from app.config import settings
from app.core.clock import utcnow

logger = logging.getLogger("personal_job_agent.stair_matcher")

class StairMatcher:
    """
    STAIR (STructure Aware Information Retriever) Matching Engine.
    Inspired by IBM STAIR research (2609.03874v2.pdf) & candidate profile context.

    Rather than treating resume and job descriptions as flat text chunks, STAIR
    exploits structured sections:
    - Language & Framework requirements vs candidate skills
    - Architectural competencies (Clean Arch, CQRS, RLS, Outbox, Concurrency)
    - Seniority constraints (1-4 YOE vs 5+ exclusion filter)
    - Location & remote feasibility (India, Hyderabad, Remote APAC/India)
    """

    ROLE_PATTERNS = {
        "ROLE 1 — Backend Engineer": [
            r"backend\s+(?:engineer|developer|software\s+engineer)",
            r"software\s+engineer[,\s-]+backend",
            r"python\s+backend",
            r"api\s+engineer"
        ],
        "ROLE 2 — AI Backend Engineer": [
            r"ai\s+backend",
            r"ai\s+(?:software\s+engineer|engineer|application\s+engineer)",
            r"applied\s+ai\s+engineer",
            r"ml\s+backend",
            r"ai\s+platform"
        ],
        "ROLE 3 — Product Engineer": [
            r"product\s+engineer",
            r"software\s+product\s+engineer",
            r"full\s*stack\s+product\s+engineer"
        ],
        "ROLE 4 — Full-Stack Engineer": [
            r"full[- ]?stack\s+(?:engineer|developer|software\s+engineer)",
            r"software\s+engineer[,\s-]+full[- ]?stack"
        ],
        "ROLE 5 — Software Engineer II / SDE II": [
            r"software\s+engineer\s+(?:ii|2)",
            r"sde\s+(?:ii|2)",
            r"engineer\s+(?:ii|2)"
        ],
        "ROLE 6 — Platform Engineer": [
            r"platform\s+engineer",
            r"backend\s+platform"
        ],
        "ROLE 7 — Applied AI Engineer": [
            r"applied\s+ai",
            r"ai\s+solutions\s+engineer"
        ],
        "ROLE 8 — Flutter / Mobile Engineer": [
            r"flutter\s+(?:developer|engineer)",
            r"mobile\s+(?:engineer|developer)"
        ],
        "ROLE 9 — Technical Solutions Engineer": [
            r"technical\s+solutions\s+engineer",
            r"implementation\s+engineer",
            r"integration\s+engineer"
        ],
        "ROLE 10 — Document AI / IDP": [
            r"document\s+ai",
            r"intelligent\s+document\s+processing",
            r"ocr\s+engineer"
        ],
        "ROLE 11 — Forward Deployed Engineer": [
            r"forward\s+deployed\s+engineer",
            r"fde"
        ]
    }

    def __init__(self, profile_path: Path = None):
        self.profile_path = profile_path or settings.CANDIDATE_PROFILE_JSON
        self.profile = self._load_profile()
        self._setup_profile_skills_and_weights()
        self._flatten_candidate_skills()

    def _setup_profile_skills_and_weights(self):
        skills = self.profile.get("skills", {})
        if "primary" in skills and "specialized" in skills and "generic" in skills:
            self.primary_skills = [s.lower() for s in skills["primary"]]
            self.specialized_skills = [s.lower() for s in skills["specialized"]]
            self.generic_skills = [s.lower() for s in skills["generic"]]
        else:
            logger.warning("Profile missing skills.primary/specialized/generic; falling back to hardcoded defaults.")
            self.primary_skills = self.PRIMARY_CORE_SKILLS
            self.specialized_skills = self.SPECIALIZED_TOOLS
            self.generic_skills = self.GENERIC_TOOLS

        weights = self.profile.get("skill_weights", {})
        self.weight_primary = float(weights.get("primary", 10.0))
        self.weight_specialized = float(weights.get("specialized", 4.5))
        self.weight_generic = float(weights.get("generic", 1.5))

    def candidate_years(self, today: Optional[datetime] = None) -> float:
        """
        Computes candidate experience in years from career_start in UTC, rounded to 0.1.
        """
        start_str = self.profile.get("career_start", "2024-07-01")
        try:
            career_start = datetime.strptime(start_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            career_start = datetime(2024, 7, 1, tzinfo=timezone.utc)

        current = today if today is not None else utcnow()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)

        diff_days = (current - career_start).total_seconds() / 86400.0
        return round(max(0.0, diff_days / 365.25), 1)

    @staticmethod
    def parse_experience_range(text: Optional[str]) -> Optional[Tuple[float, Optional[float]]]:
        """
        Parses experience ranges robustly from text:
        - '2-4 years', '1 to 3 years of experience' -> (2.0, 4.0), (1.0, 3.0)
        - '3+ yrs', 'minimum 2 years', 'at least 3 years' -> (3.0, None), (2.0, None)
        - '5 years of experience', '5 years' -> (5.0, 5.0)
        Returns (min_years, max_years) or None if no experience requirement stated.
        """
        if not text:
            return None
        cleaned = re.sub(r"\b\d+\s*(?:years?|yrs?)\s+ago\b", "", text.lower())

        # 1. Ranges: 2-4 years, 1 to 3 yrs, 2 - 4 YOE
        range_match = re.search(
            r"\b(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?|yoe)(?:\s+of\s+(?:[\w\s-]+\s+)?experience)?\b",
            cleaned,
        )
        if range_match:
            return float(range_match.group(1)), float(range_match.group(2))

        # 2. Plus / minimum / at least: 3+ years, minimum 2 years, at least 3 yrs
        plus_match = re.search(
            r"\b(?:minimum|min\.?|at\s+least)\s*(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?|yoe)(?:\s+of\s+(?:[\w\s-]+\s+)?experience)?\b",
            cleaned,
        )
        if plus_match:
            return float(plus_match.group(1)), None

        plus_suffix = re.search(
            r"\b(\d+(?:\.\d+)?)\s*\+\s*(?:years?|yrs?|yoe)(?:\s+of\s+(?:[\w\s-]+\s+)?experience)?\b",
            cleaned,
        )
        if plus_suffix:
            return float(plus_suffix.group(1)), None

        # 3. Explicit experience requirement: '5 years of experience', 'with 2 years experience'
        exact_match = re.search(
            r"(?:\b(?:with|have|has|having|require[sd]?|needing)\s+)?(\d+(?:\.\d+)?)\s*(?:years?|yrs?|yoe)\s+(?:of\s+)?(?:[\w\s-]+\s+)?experience\b",
            cleaned,
        )
        if exact_match:
            val = float(exact_match.group(1))
            return val, val

        # 4. Standalone 'X years' requirement
        standalone = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:years?|yrs?|yoe)\b", cleaned)
        if standalone:
            val = float(standalone.group(1))
            if 0.5 <= val <= 25.0:
                return val, val

        return None

    def _load_profile(self) -> Dict[str, Any]:
        if self.profile_path and self.profile_path.exists():
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _flatten_candidate_skills(self):
        self.candidate_skills = set()
        skills_dict = self.profile.get("skills", {})
        for category, skill_list in skills_dict.items():
            for s in skill_list:
                self.candidate_skills.add(s.lower())

        # Add core synonyms & keywords
        self.candidate_skills.update([
            "python", "fastapi", "flask", "c#", ".net", ".net 8", "asp.net core",
            "ef core", "sql server", "postgresql", "postgres", "redis", "celery",
            "docker", "docker compose", "alembic", "prisma", "flutter", "dart",
            "react", "next.js", "nextjs", "typescript", "javascript", "sql",
            "rest api", "rest", "api", "websocket", "websockets", "signalr",
            "mediatr", "cqrs", "clean architecture", "microservices", "onnx",
            "ocr", "paddleocr", "embeddings", "rag", "git", "github actions",
            "ci/cd", "aws", "gcp", "render", "linux"
        ])

    def classify_role(self, title: str, description: str) -> Tuple[str, str]:
        """Classifies role title into one of the 11 target roles and priority tier."""
        text = f"{title} {description[:300]}".lower()

        for role_name, patterns in self.ROLE_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, text, re.IGNORECASE):
                    tier = "P1"
                    if "P2" in role_name:
                        tier = "P2"
                    elif "P3" in role_name:
                        tier = "P3"
                    return role_name, tier

        # Fallback heuristic
        if "backend" in text or "python" in text:
            return "ROLE 1 — Backend Engineer", "P1"
        elif "ai" in text or "llm" in text:
            return "ROLE 2 — AI Backend Engineer", "P1"
        elif "full stack" in text or "fullstack" in text:
            return "ROLE 4 — Full-Stack Engineer", "P1"
        elif "flutter" in text or "mobile" in text:
            return "ROLE 8 — Flutter / Mobile Engineer", "P2"

        return "Software Engineer", "P1"

    INDIAN_STATES = [
        "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
        "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
        "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
        "nagaland", "odisha", "orissa", "punjab", "rajasthan", "sikkim", "tamil nadu",
        "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal",
        "delhi", "jammu and kashmir", "ladakh", "chandigarh", "puducherry"
    ]

    INDIAN_STATE_CODES = [
        "ts", "tg", "ka", "mh", "tn", "ap", "dl", "hr", "up", "gj", "kl",
        "wb", "rj", "mp", "pb", "od", "or", "ga", "ut", "jh", "br", "as", "ch"
    ]

    INDIAN_CITIES = [
        # South
        "bengaluru", "bangalore", "hyderabad", "secunderabad", "cyberabad", "chennai",
        "kochi", "cochin", "trivandrum", "thiruvananthapuram", "calicut", "kozhikode",
        "thrissur", "coimbatore", "madurai", "trichy", "tiruchirappalli", "salem",
        "tirunelveli", "vellore", "hosur", "mysore", "mysuru", "mangalore", "mangaluru",
        "hubli", "hubballi", "dharwad", "belgaum", "belagavi", "visakhapatnam", "vizag",
        "vijayawada", "guntur", "tirupati", "kakinada", "rajahmundry", "nellore",
        "warangal", "karimnagar", "khammam", "nizamabad", "amaravati",
        # West & Central
        "mumbai", "navi mumbai", "thane", "pune", "pimpri", "chinchwad", "nagpur", "nashik",
        "aurangabad", "chhatrapati sambhajinagar", "solapur", "kolhapur", "ahmedabad",
        "gandhinagar", "surat", "vadodara", "baroda", "rajkot", "indore", "bhopal",
        "gwalior", "jabalpur", "panaji", "panjim", "margao", "vasco", "raipur", "bilaspur",
        # North
        "delhi", "new delhi", "gurgaon", "gurugram", "noida", "greater noida", "ghaziabad",
        "faridabad", "chandigarh", "mohali", "panchkula", "ludhiana", "amritsar",
        "jalandhar", "jaipur", "udaipur", "jodhpur", "kota", "lucknow", "kanpur",
        "agra", "varanasi", "prayagraj", "allahabad", "bareilly", "meerut", "dehradun",
        "haridwar", "rishikesh", "shimla", "dharamshala",
        # East & North East
        "kolkata", "howrah", "durgapur", "siliguri", "bhubaneswar", "cuttack", "rourkela",
        "patna", "ranchi", "jamshedpur", "dhanbad", "guwahati", "shillong"
    ]

    DISQUALIFIED_REGIONS = [
        "us only", "u.s. only", "usa only", "united states only", "must be in us",
        "must be located in us", "must be located in the us", "must reside in us",
        "must reside in the us", "must reside in the united states", "us / canada only",
        "us or canada only", "us-based", "us based only", "within the us",
        "north america only", "uk only", "united kingdom only", "must reside in uk",
        "must be in uk", "canada only", "australia only", "europe only", "eu only",
        "must reside in europe", "emea only", "latam only", "latin america only",
        "us citizen", "security clearance", "w2 only", "no c2c",
        "north america", "united states", "canada", "europe", "emea", "amer", "latam",
        "poland", "germany", "united kingdom", "france", "australia", "singapore"
    ]

    NON_INDIA_CITIES = [
        "san francisco", "new york", "nyc", "seattle", "austin", "chicago",
        "los angeles", "boston", "london", "berlin", "amsterdam", "paris",
        "dublin", "munich", "toronto", "vancouver", "sydney", "melbourne",
        "singapore", "tokyo", "zurich", "warsaw", "krakow", "dubai"
    ]

    PRIMARY_CORE_SKILLS = [
        "python", "fastapi", "flask", "c#", ".net", ".net 8", "asp.net",
        "asp.net core", "flutter", "react", "next.js", "nextjs", "typescript"
    ]

    SPECIALIZED_TOOLS = [
        "postgresql", "postgres", "redis", "docker", "celery", "prisma", "alembic",
        "signalr", "mediatr", "clean architecture", "cqrs", "onnx", "ocr", "paddleocr",
        "embeddings", "rag", "supabase"
    ]

    GENERIC_TOOLS = [
        "sql", "rest", "api", "aws", "gcp", "render", "linux", "git", "websockets"
    ]

    @staticmethod
    def match_skill(skill: str, text: str) -> bool:
        """Punctuation-safe skill matcher handling C#, .NET, C++, and standard word boundaries."""
        s = skill.lower()
        if s == "c#":
            return bool(re.search(r"(?<![\w])c#(?![\w])", text))
        elif s in (".net", ".net core", "asp.net core", "asp.net", ".net 8"):
            return bool(re.search(r"(?<![\w])(?:\.net|asp\.net)(?:\s*(?:8|core|\b))?(?![\w])", text))
        elif s == "c++":
            return bool(re.search(r"(?<![\w])c\+\+(?![\w])", text))
        elif s in ("next.js", "nextjs"):
            return bool(re.search(r"\bnext(?:\.js|js)\b", text))
        else:
            return bool(re.search(rf"\b{re.escape(s)}\b", text))

    DISQUALIFIED_PRIMARY_STACKS = [
        r"\bjava\b", r"\bspring\s+boot\b", r"\bspring\b", r"\bgolang\b",
        r"\brust\b", r"\bruby\b", r"\bruby\s+on\s+rails\b", r"\brails\b",
        r"\bphp\b", r"\blaravel\b", r"\bscala\b", r"\bsalesforce\b", r"\bapex\b",
        r"\bc\+\+\b", r"\bcpp\b"
    ]

    def evaluate_location(self, location: str, description: str, title: str = "") -> Tuple[bool, float, str, str]:
        """
        Validates location feasibility according to candidate preference:
        STRICT REQUIREMENT: All work from office, hybrid, and remote roles from all over India.
        Supports all Indian cities (tier 1, tier 2, tier 3), state codes (TS, KA, MH, etc.), and pan-India remote.
        Disqualifies foreign onsite, foreign remote, EMEA, AMER, US, Europe, and unrestricted global remote.
        Returns: (is_eligible, score, category, reason)
        """
        loc_clean = (location or "").lower().strip()
        title_lower = (title or "").lower().strip()
        desc_sample = description[:1500].lower()

        # 0. Check regional tags in Title (e.g. "Support Engineer (EMEA)" or "(AMER)" or "(Europe)")
        if re.search(r"\b(emea|amer|americas|latam|europe|us|uk|apac)\b", title_lower) and not re.search(r"\b(india)\b", title_lower):
            matched_reg = re.search(r"\b(emea|amer|americas|latam|europe|us|uk|apac)\b", title_lower).group(1).upper()
            return False, 0.0, "Excluded (Restricted Region)", f"Title restricted to non-India region '{matched_reg}'"

        # Special Branch: Empty or Unknown location handling
        if not loc_clean or loc_clean in ("unknown", "unspecified", "none", "null"):
            # 1. Scan description for exclusions
            for disq in self.DISQUALIFIED_REGIONS:
                if re.search(rf"\b{re.escape(disq)}\b", desc_sample):
                    return False, 0.0, "Excluded (Restricted Region)", f"Description restricted to '{disq}'"
            for city in self.NON_INDIA_CITIES:
                if re.search(rf"\b{re.escape(city)}\b", desc_sample):
                    return False, 0.0, "Excluded (Non-India Onsite)", f"Description mentions foreign location: '{city}'"

            # 2. Scan description for explicit India eligibility
            has_india_phrase = bool(
                re.search(r"\b(india|work from india|working from india|based in india|hiring in india|ist)\b", desc_sample)
            )
            has_indian_city = any(re.search(rf"\b{re.escape(c)}\b", desc_sample) for c in self.INDIAN_CITIES)
            if has_india_phrase or has_indian_city:
                return True, 25.0, "Remote (India, from posting)", "India eligibility explicitly mentioned in posting description"

            # 3. Otherwise: LOCATION_UNVERIFIED and score 0
            return False, 0.0, "LOCATION_UNVERIFIED", "Location is unknown and description lacks explicit India confirmation"

        # 1. Check for foreign indicators if 'india' is not explicitly in location
        if "india" not in loc_clean:
            for disq in self.DISQUALIFIED_REGIONS:
                if re.search(rf"\b{re.escape(disq)}\b", loc_clean):
                    return False, 0.0, "Excluded (Restricted Region)", f"Restricted to '{disq}'"
            for city in self.NON_INDIA_CITIES:
                if re.search(rf"\b{re.escape(city)}\b", loc_clean):
                    return False, 0.0, "Excluded (Non-India Onsite)", f"Location outside India: {location}"

        # 2. Check explicit 'india' (handles 'TS, India', 'KA, India', 'Remote - India', etc.)
        if "india" in loc_clean:
            if "remote" in loc_clean or "remote" in desc_sample[:300] or "work from home" in desc_sample[:300]:
                return True, 25.0, "Remote (India)", f"Remote role anywhere in India: {location}"
            if "hybrid" in loc_clean or "hybrid" in desc_sample[:300]:
                return True, 25.0, "India Hybrid", f"Hybrid position in India: {location}"
            return True, 25.0, "India Onsite (Office)", f"Work from office in India: {location}"

        # 3. Check all Indian cities (mainstream and non-mainstream across all states)
        for city in self.INDIAN_CITIES:
            if re.search(rf"\b{re.escape(city)}\b", loc_clean):
                if "remote" in loc_clean or "remote" in desc_sample[:300]:
                    return True, 25.0, f"Remote ({city.title()})", f"Remote role based in {city.title()}"
                if "hybrid" in loc_clean or "hybrid" in desc_sample[:300]:
                    return True, 25.0, f"Hybrid ({city.title()})", f"Hybrid role in {city.title()}"
                return True, 25.0, f"Onsite ({city.title()})", f"Work from office in {city.title()}"

        # 4. Check all Indian states (full name)
        for state in self.INDIAN_STATES:
            if re.search(rf"\b{re.escape(state)}\b", loc_clean):
                if "remote" in loc_clean or "remote" in desc_sample[:300]:
                    return True, 25.0, f"Remote ({state.title()})", f"Remote role in {state.title()}"
                return True, 25.0, f"India Onsite ({state.title()})", f"Office/Hybrid in {state.title()}"

        # 5. Check Indian state abbreviations (TS, KA, MH, TN, AP, DL, HR, UP, GJ, KL, WB, RJ, MP, PB, etc.)
        for code in self.INDIAN_STATE_CODES:
            if re.search(rf"\b{code}\b", loc_clean):
                return True, 25.0, f"India ({code.upper()})", f"Position in Indian state code: {code.upper()}"

        # 6. Check if description explicitly mentions India office or India remote
        if any(ind in desc_sample[:400] for ind in ["india", "bengaluru", "bangalore", "hyderabad", "pune", "mumbai", "gurgaon", "noida", "chennai"]):
            return True, 25.0, "Remote (India)", f"India location explicitly mentioned in posting: {location}"

        # Disqualify all non-India, worldwide generic remote, and unrestricted foreign locations
        return False, 0.0, "Excluded (Location Mismatch)", f"Location '{location}' is not located in or hiring from India"

    def evaluate_match(
        self,
        title: str,
        company: str,
        location: str,
        description: str,
        today: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Structure-Aware evaluation of a job posting against candidate profile.
        Returns match score (0-100), tier, breakdown, matched/missing skills, and verdict.
        """
        desc_lower = description.lower()
        title_lower = title.lower()

        role_category, tier = self.classify_role(title, description)

        # 1. Negative Filter Checks (Title Level Disqualifiers)
        cy = self.candidate_years(today)
        raw_blocklist = self.profile.get("title_blocklist")
        if raw_blocklist:
            blocklist = [t.lower() for t in raw_blocklist]
        else:
            blocklist = [
                "intern", "internship", "trainee", "fresher",
                "senior", "sr", "lead", "architect", "staff", "principal",
                "engineering manager", "manager", "vp", "director", "head of",
                "qa", "sdet", "test engineer", "quality assurance", "automation tester",
                "security engineer", "infosec", "embedded", "firmware", "hardware"
            ]

        # Allow senior titles once candidate_years crosses 3.0
        if cy >= 3.0:
            senior_terms = {"senior", "sr", "lead", "staff", "principal"}
            blocklist = [t for t in blocklist if t not in senior_terms]

        for disq in blocklist:
            if re.search(rf"\b{re.escape(disq)}\b", title_lower):
                return {
                    "score": 15.0,
                    "tier": "Excluded",
                    "role_category": role_category,
                    "verdict": f"Excluded due to title level/role disqualifier: '{disq}'",
                    "matched_skills": [],
                    "missing_skills": [],
                    "location_category": "Excluded",
                    "location_feasibility": "Title Disqualified",
                    "recommendation": "Skip",
                }

        # Check for disqualified primary tech in title (e.g. Java Engineer, Go Engineer)
        for disq_tech in self.DISQUALIFIED_PRIMARY_STACKS:
            if re.search(disq_tech, title_lower):
                return {
                    "score": 15.0,
                    "tier": "Excluded (Tech Mismatch)",
                    "role_category": role_category,
                    "verdict": f"Excluded due to non-matching primary tech in title: '{disq_tech}'",
                    "matched_skills": [],
                    "missing_skills": [],
                    "location_category": "Excluded",
                    "location_feasibility": "Tech Disqualified",
                    "recommendation": "Skip",
                }

        # 2. Location Feasibility Gate (Strictly India Only)
        is_loc_eligible, loc_score, loc_cat, loc_detail = self.evaluate_location(location, description, title=title)
        if not is_loc_eligible:
            tier_name = (
                "Excluded (Location Unverified)"
                if loc_cat == "LOCATION_UNVERIFIED"
                else ("Excluded (Restricted Region)" if "Restricted" in loc_cat else "Excluded (Location)")
            )
            return {
                "score": 0.0 if loc_cat == "LOCATION_UNVERIFIED" else 15.0,
                "tier": tier_name,
                "role_category": role_category,
                "matched_skills": [],
                "missing_skills": [],
                "location_category": loc_cat,
                "location_feasibility": loc_detail,
                "verdict": f"Excluded due to location: {loc_detail}",
                "recommendation": "Skip",
            }

        # 3. Technical Stack Alignment with Weighted Skill Taxonomy
        found_matches = []
        weighted_points = 0.0

        for ps in self.primary_skills:
            if self.match_skill(ps, desc_lower) or self.match_skill(ps, title_lower):
                if ps not in found_matches:
                    found_matches.append(ps)
                    weighted_points += self.weight_primary

        for st in self.specialized_skills:
            if self.match_skill(st, desc_lower):
                if st not in found_matches:
                    found_matches.append(st)
                    weighted_points += self.weight_specialized

        for gt in self.generic_skills:
            if self.match_skill(gt, desc_lower):
                if gt not in found_matches:
                    found_matches.append(gt)
                    weighted_points += self.weight_generic

        # Candidate MUST have at least one primary core stack match
        has_primary_core = any(
            self.match_skill(ps, desc_lower) or self.match_skill(ps, title_lower)
            for ps in self.primary_skills
        )
        if not has_primary_core:
            return {
                "score": 15.0,
                "tier": "Excluded (Tech Mismatch)",
                "role_category": role_category,
                "matched_skills": found_matches,
                "missing_skills": self.primary_skills[:4],
                "location_category": loc_cat,
                "location_feasibility": loc_detail,
                "verdict": "Excluded: Job does not require any core resume technology",
                "recommendation": "Skip",
            }

        potential_skills = ["kubernetes", "kafka", "graphql", "go", "java", "terraform"]
        missing_skills = [s for s in potential_skills if re.search(rf"\b{s}\b", desc_lower) and s not in found_matches]

        # 4. Technical Stack Alignment Score (Up to 40 pts)
        tech_score = min(40.0, round(weighted_points, 1))

        # 5. Seniority & Experience Assessment (Max 35 pts)
        prelim_score = 35.0 + tech_score + loc_score

        exp_range = self.parse_experience_range(description)
        tolerance = float(self.profile.get("experience_tolerance_years", 1.0))
        cy = self.candidate_years(today)
        is_strong_match = has_primary_core and (prelim_score >= 80.0)

        if exp_range is not None:
            min_yoe, max_yoe = exp_range
            max_allowed = (cy + tolerance) if is_strong_match else cy

            if min_yoe > max_allowed:
                return {
                    "score": 15.0,
                    "tier": "Excluded (Experience)",
                    "role_category": role_category,
                    "matched_skills": found_matches,
                    "missing_skills": missing_skills,
                    "location_category": loc_cat,
                    "location_feasibility": loc_detail,
                    "verdict": f"Excluded: Stated experience requirement exceeds candidate ceiling ({max_allowed:.1f} YOE)",
                    "recommendation": "Skip",
                }

            if min_yoe > cy and is_strong_match:
                seniority_score = 30.0
                exp_note = f"Stated {min_yoe} YOE accepted under strong match allowance ({prelim_score:.1f} prelim score)"
            else:
                seniority_score = 35.0
                exp_note = f"Within candidate experience ceiling ({min_yoe} YOE <= {cy:.1f} YOE)"
        else:
            # When posting states no years, do not penalize
            seniority_score = 35.0
            exp_note = "No stated experience requirement (no penalty applied)"

        # Total STAIR score (Seniority max 35 + Tech max 40 + Location max 25 = 100 max)
        total_score = min(100.0, round(seniority_score + tech_score + loc_score, 1))

        verdict = (
            f"Role matched as {role_category} ({tier}). Location: {loc_cat}. "
            f"Experience: {exp_note}. Found {len(found_matches)} core stack overlaps ({', '.join(found_matches[:5])})."
        )

        return {
            "score": total_score,
            "tier": tier,
            "role_category": role_category,
            "matched_skills": found_matches,
            "missing_skills": missing_skills,
            "location_category": loc_cat,
            "location_feasibility": loc_detail,
            "verdict": verdict,
            "recommendation": "Apply" if total_score >= 70.0 else ("Consider" if total_score >= 50.0 else "Skip"),
        }
