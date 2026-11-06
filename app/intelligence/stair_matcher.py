import json
import re
from pathlib import Path
from typing import Dict, List, Any, Tuple
from app.config import settings

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
        self._flatten_candidate_skills()

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
        r"\bphp\b", r"\blaravel\b", r"\bscala\b", r"\bsalesforce\b", r"\bapex\b"
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
        combined = f"{title_lower} {loc_clean} {desc_sample}"

        # 0. Check regional tags in Title (e.g. "Support Engineer (EMEA)" or "(AMER)" or "(Europe)")
        if re.search(r"\b(emea|amer|americas|latam|europe|us|uk|apac)\b", title_lower) and not re.search(r"\b(india)\b", title_lower):
            matched_reg = re.search(r"\b(emea|amer|americas|latam|europe|us|uk|apac)\b", title_lower).group(1).upper()
            return False, 0.0, "Excluded (Restricted Region)", f"Title restricted to non-India region '{matched_reg}'"

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

    def evaluate_match(self, title: str, company: str, location: str, description: str) -> Dict[str, Any]:
        """
        Structure-Aware evaluation of a job posting against Meghraj's profile.
        Returns match score (0-100), tier, breakdown, matched/missing skills, and verdict.
        """
        desc_lower = description.lower()
        title_lower = title.lower()
        full_text = f"{title_lower} {desc_lower}"

        role_category, tier = self.classify_role(title, description)

        # 1. Negative Filter Checks (Title Level Disqualifiers)
        hard_disqualifiers = [
            r"\bintern\b", r"\binternship\b", r"\btrainee\b", r"\bfresher\b",
            r"\b0\s*years\b", r"\b0-1\s*years?\b",
            r"\bsenior\b", r"\bsr\.?\b", r"\blead\b", r"\barchitect\b",
            r"\bstaff\b", r"\bprincipal\b",
            r"\bengineering\s+manager\b", r"\bmanager\b", r"\bvp\b", r"\bdirector\b",
            r"\bhead\s+of\b", r"\bl5\b", r"\bl6\b", r"\bl7\b",
            r"\bsde\s+iii\b", r"\bsoftware\s+engineer\s+iii\b", r"\bengineer\s+iii\b",
            r"\bqa\b", r"\bsdet\b", r"\btest\s+engineer\b", r"\bquality\s+assurance\b",
            r"\bautomation\s+tester\b", r"\bsecurity\s+engineer\b", r"\binfosec\b",
            r"\bembedded\b", r"\bfirmware\b", r"\bhardware\b"
        ]
        
        for disq in hard_disqualifiers:
            if re.search(disq, title_lower):
                return {
                    "score": 15.0,
                    "tier": "Excluded",
                    "role_category": role_category,
                    "verdict": f"Excluded due to title level/role disqualifier: '{disq}'",
                    "matched_skills": [],
                    "missing_skills": [],
                    "location_category": "Excluded",
                    "location_feasibility": "Title Disqualified",
                    "recommendation": "Skip"
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
                    "recommendation": "Skip"
                }

        # 2. Location Feasibility Gate (Strictly India Only)
        is_loc_eligible, loc_score, loc_cat, loc_detail = self.evaluate_location(location, description, title=title)
        if not is_loc_eligible:
            return {
                "score": 15.0,
                "tier": "Excluded (Location)",
                "role_category": role_category,
                "matched_skills": [],
                "missing_skills": [],
                "location_category": loc_cat,
                "location_feasibility": loc_detail,
                "verdict": f"Excluded due to location: {loc_detail}",
                "recommendation": "Skip"
            }

        # 3. Technical Stack Alignment with Weighted Skill Taxonomy
        # Weight 5: Primary Core Skills (Python, FastAPI, C#, .NET, React, TypeScript, Flutter)
        # Weight 3: Databases & Specialized Tools (Postgres, Redis, Docker, Celery, Prisma, etc.)
        # Weight 1: Generic & Auxiliary Tools (SQL, REST, API, Git, Linux, AWS, GCP)
        found_matches = []
        weighted_points = 0.0

        for ps in self.PRIMARY_CORE_SKILLS:
            if self.match_skill(ps, desc_lower) or self.match_skill(ps, title_lower):
                if ps not in found_matches:
                    found_matches.append(ps)
                    weighted_points += 10.0 # Weight 5

        for st in self.SPECIALIZED_TOOLS:
            if self.match_skill(st, desc_lower):
                if st not in found_matches:
                    found_matches.append(st)
                    weighted_points += 4.5 # Weight 3

        for gt in self.GENERIC_TOOLS:
            if self.match_skill(gt, desc_lower):
                if gt not in found_matches:
                    found_matches.append(gt)
                    weighted_points += 1.5 # Weight 1

        # Candidate MUST have at least one primary core stack match (Python, C#/.NET, React, Flutter, etc.)
        has_primary_core = any(
            self.match_skill(ps, desc_lower) or self.match_skill(ps, title_lower)
            for ps in self.PRIMARY_CORE_SKILLS
        )
        if not has_primary_core:
            return {
                "score": 15.0,
                "tier": "Excluded (Tech Mismatch)",
                "role_category": role_category,
                "matched_skills": found_matches,
                "missing_skills": self.PRIMARY_CORE_SKILLS[:4],
                "location_category": loc_cat,
                "location_feasibility": loc_detail,
                "verdict": "Excluded: Job does not require any core resume technology (Python, C#/.NET, React/TypeScript, Flutter)",
                "recommendation": "Skip"
            }

        potential_skills = ["kubernetes", "kafka", "graphql", "go", "java", "terraform"]
        missing_skills = [s for s in potential_skills if re.search(rf"\b{s}\b", desc_lower) and s not in found_matches]

        # 4. Technical Stack Alignment Score (Up to 40 pts)
        tech_score = min(40.0, round(weighted_points, 1))

        # 5. Seniority & Experience Assessment (Max 35 pts)
        # Candidate rule: 0 to 2 years 3 months (0 - 2.25 YOE).
        # Up to 3 years allowed ONLY if resume is a strong match (core stack, >=3 tech overlaps, score >= 75%).
        # Absolutely NOTHING higher than 3 years.
        desc_clean = re.sub(r"[0-9]+\s*(?:years?|yrs?)\s+ago", "", desc_lower)

        # Tokenize experience mentions
        range_pat = re.compile(r"\b([0-9]+(?:\.[0-9]+)?)\s*(?:-|to)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:\+)?\s*(?:years?|yrs?|yoe)\b")
        plus_pat = re.compile(r"\b([0-9]+(?:\.[0-9]+)?)\s*\+\s*(?:years?|yrs?|yoe)\b")
        min_pat = re.compile(r"\b(?:minimum|min|at\s+least)\s+([0-9]+(?:\.[0-9]+)?)\s*(?:years?|yrs?|yoe)\b")
        exact_pat = re.compile(r"(?:\b(?:with|have|has|having|requires?|needing)\s+)?([0-9]+(?:\.[0-9]+)?)\s*(?:years?|yrs?|yoe)\s+(?:of\s+)?(?:relevant\s+|hands-on\s+|industry\s+|professional\s+|work\s+)?experience\b")

        yoe_tokens = []
        def _mask_range(m):
            yoe_tokens.append(("range", float(m.group(1)), float(m.group(2)), m.group(0)))
            return " " * len(m.group(0))

        masked_text = range_pat.sub(_mask_range, desc_clean)

        for m in plus_pat.finditer(masked_text):
            val = float(m.group(1))
            yoe_tokens.append(("plus", val, val + 2.0, m.group(0)))

        for m in min_pat.finditer(masked_text):
            val = float(m.group(1))
            yoe_tokens.append(("min", val, val, m.group(0)))

        for m in exact_pat.finditer(masked_text):
            val = float(m.group(1))
            yoe_tokens.append(("exact", val, val, m.group(0)))

        # Rule 1: Strictly > 3 years ceiling ("nothing higher than 3")
        for kind, low, high, raw in yoe_tokens:
            if kind in ("plus", "min", "exact") and low > 3.0:
                return {
                    "score": 15.0,
                    "tier": "Excluded (Experience > 3 YOE)",
                    "role_category": role_category,
                    "matched_skills": found_matches,
                    "missing_skills": missing_skills,
                    "location_category": loc_cat,
                    "location_feasibility": loc_detail,
                    "verdict": f"Excluded: Required experience ({raw}) strictly exceeds candidate ceiling of 3 years",
                    "recommendation": "Skip"
                }
            if kind == "range":
                if low > 3.0 or (low >= 3.0 and high > 3.0) or (low > 2.25 and high > 3.0):
                    return {
                        "score": 15.0,
                        "tier": "Excluded (Experience > 3 YOE)",
                        "role_category": role_category,
                        "matched_skills": found_matches,
                        "missing_skills": missing_skills,
                        "location_category": loc_cat,
                        "location_feasibility": loc_detail,
                        "verdict": f"Excluded: Required experience range ({raw}) strictly exceeds candidate ceiling of 3 years",
                        "recommendation": "Skip"
                    }

        # Rule 2: ~3 YOE checks ("or 3 if my resume is a strong match")
        prelim_score = 30.0 + tech_score + loc_score
        is_strong_match = has_primary_core and (len(found_matches) >= 3) and (prelim_score >= 75.0)

        requires_strong = False
        strong_reason = ""
        for kind, low, high, raw in yoe_tokens:
            if kind in ("plus", "min", "exact") and 2.25 < low <= 3.0:
                requires_strong = True
                strong_reason = raw
                break
            if kind == "range" and (high > 2.25 or (low <= 2.25 and high >= 3.0)):
                requires_strong = True
                strong_reason = raw
                break

        if requires_strong:
            if not is_strong_match:
                return {
                    "score": 15.0,
                    "tier": "Excluded (Experience 3 YOE - Needs Strong Match)",
                    "role_category": role_category,
                    "matched_skills": found_matches,
                    "missing_skills": missing_skills,
                    "location_category": loc_cat,
                    "location_feasibility": loc_detail,
                    "verdict": f"Excluded: Role asks for ~3 YOE ({strong_reason}), but candidate profile is not a strong match (needs score >= 75% with core stack)",
                    "recommendation": "Skip"
                }
            seniority_score = 30.0
            exp_note = f"~3 YOE ({strong_reason}) accepted due to strong stack match ({prelim_score}%)"
        else:
            # 0 to 2 years 3 months primary band
            has_primary_band = bool(re.search(r"0-2|0\s*to\s*2|1-2|1\s*to\s*2|0-1|0\s*to\s*1|fresher|junior|associate", full_text))
            seniority_score = 35.0 if has_primary_band else 30.0
            exp_note = "Within candidate primary band (0 to 2 years 3 months)"
            exp_note = "Within candidate primary band (0 to 2 years 3 months)"

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
            "recommendation": "Apply" if total_score >= 70.0 else ("Consider" if total_score >= 50.0 else "Skip")
        }
