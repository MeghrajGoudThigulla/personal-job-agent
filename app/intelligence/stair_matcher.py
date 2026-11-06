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

    INDIA_LOCATIONS = [
        "india", "hyderabad", "bengaluru", "bangalore", "pune", "mumbai",
        "gurgaon", "gurugram", "noida", "delhi", "new delhi", "chennai",
        "coimbatore", "ahmedabad", "kolkata", "chandigarh", "kochi",
        "kerala", "karnataka", "telangana", "maharashtra", "tamil nadu",
        "mysore", "indore", "jaipur"
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
        "poland", "germany", "united kingdom", "france", "australia"
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

    DISQUALIFIED_PRIMARY_STACKS = [
        r"\bjava\b", r"\bspring\s+boot\b", r"\bspring\b", r"\bgolang\b",
        r"\brust\b", r"\bruby\b", r"\bruby\s+on\s+rails\b", r"\brails\b",
        r"\bphp\b", r"\blaravel\b", r"\bscala\b", r"\bsalesforce\b", r"\bapex\b"
    ]

    def evaluate_location(self, location: str, description: str, title: str = "") -> Tuple[bool, float, str, str]:
        """
        Validates location feasibility according to candidate preference:
        STRICT REQUIREMENT: India-specific jobs only (Onsite/Hybrid in India, or Remote - India).
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

        # 1. Check standalone non-India location names
        if loc_clean in ("europe", "emea", "amer", "americas", "latam", "united states", "us", "usa", "uk", "united kingdom", "canada", "australia", "germany", "france", "north america", "poland"):
            return False, 0.0, "Excluded (Restricted Region)", f"Location restricted to {loc_clean.title()}"

        # 2. Check for hard disqualifiers in location
        for disq in self.DISQUALIFIED_REGIONS:
            if re.search(rf"\b{re.escape(disq)}\b", loc_clean):
                if not any(ind in loc_clean for ind in self.INDIA_LOCATIONS):
                    return False, 0.0, "Excluded (Restricted Region)", f"Restricted to '{disq}'"

        # 3. Check Non-India Onsite Cities
        for city in self.NON_INDIA_CITIES:
            if city in loc_clean and not any(ind in loc_clean for ind in self.INDIA_LOCATIONS):
                return False, 0.0, "Excluded (Non-India Onsite)", f"Location outside India: {location}"

        # 4. Check explicit India locations (Bangalore, Hyderabad, Pune, etc.)
        for ind_term in self.INDIA_LOCATIONS:
            if re.search(rf"\b{re.escape(ind_term)}\b", loc_clean):
                if "remote" in loc_clean or "remote" in desc_sample[:300]:
                    return True, 25.0, "Remote (India)", f"Remote role based in India ({ind_term.title()})"
                return True, 25.0, "India Onsite/Hybrid", f"India position in {ind_term.title()}"

        # 5. Check if description explicitly mentions India as an allowed hiring location
        if "india" in desc_sample[:400] or "hyderabad" in desc_sample[:400] or "bengaluru" in desc_sample[:400] or "bangalore" in desc_sample[:400]:
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

        # 3. Technical Stack Alignment
        found_matches = []
        key_tech_to_scan = [
            "python", "fastapi", "flask", "c#", ".net", "asp.net", "postgresql",
            "redis", "celery", "docker", "flutter", "react", "next.js", "typescript",
            "sql", "rest", "api", "signalr", "mediatr", "clean architecture", "cqrs",
            "supabase", "aws", "gcp", "render", "linux", "onnx", "ocr", "embeddings",
            "alembic", "prisma", "websockets"
        ]

        for tech in key_tech_to_scan:
            pattern = rf"\b{re.escape(tech)}\b"
            if re.search(pattern, desc_lower):
                found_matches.append(tech)

        # Candidate MUST have at least one primary core stack match (Python, C#/.NET, React, Flutter, etc.)
        has_primary_core = any(
            re.search(rf"\b{re.escape(ps)}\b", desc_lower) or re.search(rf"\b{re.escape(ps)}\b", title_lower)
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

        # 4. Seniority & Experience Assessment (Max 35 pts)
        has_heavy_yoe = bool(re.search(r"(?:5\+|6\+|7\+|8\+|10\+|12\+)\s*(?:years|yoe)|5\s*-\s*[6-9]\s*years", desc_lower))
        if has_heavy_yoe:
            return {
                "score": 15.0,
                "tier": "Excluded (Experience)",
                "role_category": role_category,
                "matched_skills": found_matches,
                "missing_skills": missing_skills,
                "location_category": loc_cat,
                "location_feasibility": loc_detail,
                "verdict": "Excluded: High experience requirement (5+ YOE exceeds candidate profile of 1-3 YOE)",
                "recommendation": "Skip"
            }

        seniority_score = 30.0 # base for qualified entry-to-mid roles
        has_mid_signal = bool(re.search(r"2-4|1-3|2-3|2\+|engineer ii|sde ii|mid-level", full_text))
        if has_mid_signal:
            seniority_score = 35.0 # Sweet spot for candidate

        # 5. Technical Stack Alignment Score (Up to 40 pts)
        tech_score = min(40.0, len(found_matches) * 6.0)

        # Total STAIR score (Seniority max 35 + Tech max 40 + Location max 25 = 100 max)
        total_score = min(100.0, round(seniority_score + tech_score + loc_score, 1))

        verdict = (
            f"Role matched as {role_category} ({tier}). Location: {loc_cat}. "
            f"Found {len(found_matches)} core stack overlaps ({', '.join(found_matches[:5])})."
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
