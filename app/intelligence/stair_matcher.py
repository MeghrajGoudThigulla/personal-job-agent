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
        "us citizen", "security clearance", "w2 only", "no c2c"
    ]

    GLOBAL_REMOTE_KEYWORDS = [
        "worldwide", "anywhere", "remote worldwide", "remote (worldwide)",
        "remote anywhere", "remote (anywhere)", "work from anywhere",
        "global remote", "remote (global)", "any location", "fully remote",
        "100% remote", "remote - anywhere", "all locations"
    ]

    NON_INDIA_CITIES = [
        "san francisco", "new york", "nyc", "seattle", "austin", "chicago",
        "los angeles", "boston", "london", "berlin", "amsterdam", "paris",
        "dublin", "munich", "toronto", "vancouver", "sydney", "melbourne",
        "singapore", "tokyo", "zurich"
    ]

    def evaluate_location(self, location: str, description: str) -> Tuple[bool, float, str, str]:
        """
        Validates location feasibility according to candidate preference:
        1. India-specific jobs (Onsite/Hybrid in Hyderabad, Bangalore, Pune, etc.)
        2. Remote from India (Remote - India, APAC)
        3. Remote from anywhere (Worldwide / Global / Unrestricted Remote)
        
        Disqualifies jobs restricted to other regions (US only, UK only, non-India onsite).
        Returns: (is_eligible, score, category, reason)
        """
        loc_clean = (location or "").lower().strip()
        desc_sample = description[:1500].lower()
        combined = f"{loc_clean} {desc_sample}"

        # 1. Check for hard disqualifiers (e.g. US Only, UK Only, Europe Only, Citizen restrictions)
        for disq in self.DISQUALIFIED_REGIONS:
            if re.search(rf"\b{re.escape(disq)}\b", combined):
                # If 'india' is explicitly included as an alternative, don't disqualify
                if "india" not in loc_clean and "india" not in desc_sample[:300]:
                    return False, 0.0, "Excluded (Restricted Region)", f"Restricted to '{disq}'"

        # 2. Check India-specific or India Remote
        for ind_term in self.INDIA_LOCATIONS:
            if re.search(rf"\b{re.escape(ind_term)}\b", loc_clean):
                if "remote" in loc_clean or "remote" in desc_sample:
                    return True, 25.0, "Remote (India)", f"Remote role based in India ({ind_term.title()})"
                return True, 25.0, "India Onsite/Hybrid", f"India position in {ind_term.title()}"

        # 3. Check APAC / Asia-Pacific (India-inclusive region)
        if any(term in loc_clean or term in desc_sample[:500] for term in ["apac", "asia-pacific", "south asia", "remote - asia", "remote (apac)"]):
            return True, 25.0, "Remote (APAC / India)", "Remote eligible for India / APAC candidates"

        # 4. Check Explicit Worldwide / Global / Anywhere
        for gw in self.GLOBAL_REMOTE_KEYWORDS:
            if gw in loc_clean or gw in desc_sample[:600]:
                return True, 25.0, "Remote (Worldwide / Anywhere)", f"Remote worldwide opportunity ({gw})"

        # 5. Check Unrestricted "Remote"
        if loc_clean in ("remote", "remote - global", "flexible", "work from home", "remote-first") or loc_clean.startswith("remote"):
            # Ensure description doesn't secretly require US/European presence
            if not any(non_ind in desc_sample[:600] for non_ind in ["united states", "north america", "must be based in"]):
                return True, 25.0, "Remote (Worldwide)", "Unrestricted Remote position"

        # 6. Check Non-India Onsite Cities (e.g. San Francisco, London, Berlin)
        for city in self.NON_INDIA_CITIES:
            if city in loc_clean and "india" not in loc_clean:
                return False, 0.0, "Excluded (Non-India Onsite)", f"Onsite/Hybrid outside India: {location}"

        # 7. Check if description mentions India as an option
        if "india" in desc_sample[:500] or "hyderabad" in desc_sample[:500] or "bengaluru" in desc_sample[:500]:
            return True, 25.0, "Remote (India)", f"India location mentioned in posting: {location}"

        # If location is completely foreign or unknown with no remote/India context
        return False, 0.0, "Excluded (Location Mismatch)", f"Location '{location}' is neither India nor Worldwide Remote"

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
            r"\bstaff\s+engineer\b", r"\bprincipal\s+engineer\b",
            r"\bengineering\s+manager\b", r"\bvp\s+of\s+engineering\b",
            r"\bdirector\s+of\s+engineering\b"
        ]
        
        for disq in hard_disqualifiers:
            if re.search(disq, title_lower):
                return {
                    "score": 15.0,
                    "tier": "Excluded",
                    "role_category": role_category,
                    "verdict": f"Excluded due to title level match: '{disq}'",
                    "matched_skills": [],
                    "missing_skills": [],
                    "location_category": "Excluded",
                    "location_feasibility": "Title Disqualified",
                    "recommendation": "Skip"
                }

        # 2. Location Feasibility Gate (India, Remote from India, or Remote from Anywhere)
        is_loc_eligible, loc_score, loc_cat, loc_detail = self.evaluate_location(location, description)
        
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

        potential_skills = ["kubernetes", "kafka", "graphql", "go", "java", "terraform"]
        missing_skills = [s for s in potential_skills if re.search(rf"\b{s}\b", desc_lower) and s not in found_matches]

        # If location is disqualified, drop score to 15.0 and mark as Excluded
        if not is_loc_eligible:
            return {
                "score": 15.0,
                "tier": "Excluded (Location)",
                "role_category": role_category,
                "matched_skills": found_matches,
                "missing_skills": missing_skills,
                "location_category": loc_cat,
                "location_feasibility": loc_detail,
                "verdict": f"Excluded due to location: {loc_detail}",
                "recommendation": "Skip"
            }

        # 4. Seniority Assessment (Up to 35 pts)
        seniority_score = 25.0 # base
        is_senior = bool(re.search(r"\bsenior\b|\bsr\.\b", title_lower))
        has_mid_signal = bool(re.search(r"2-4|1-3|2-3|2\+|engineer ii|sde ii|mid-level", full_text))
        has_heavy_yoe = bool(re.search(r"(?:5\+|6\+|7\+|8\+|10\+)\s*(?:years|yoe)", desc_lower))

        if has_mid_signal:
            seniority_score = 35.0 # Optimal sweet spot
        elif is_senior and not has_heavy_yoe:
            seniority_score = 30.0 # Stretch target
        elif has_heavy_yoe:
            seniority_score = 15.0 # High YOE barrier

        # 5. Technical Stack Alignment Score (Up to 40 pts)
        tech_score = min(40.0, len(found_matches) * 5.0)

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
