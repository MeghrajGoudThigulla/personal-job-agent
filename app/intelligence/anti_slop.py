import re
import json
from pathlib import Path
from typing import Dict, List, Tuple
from app.config import settings

class AntiSlopValidator:
    """
    Enforces the Slop Reduction System defined in slop-reduct.md.
    Eliminates AI buzzwords, vague corporate fluff, and generic boilerplate.
    Ensures concrete, falsifiable technical metrics and authentic engineering voice.
    """
    
    DEFAULT_PROHIBITED = [
        "seamless", "seamlessly", "robust", "powerful", "cutting-edge", 
        "game-changing", "unlock", "unlocking", "leverage", "leveraging", 
        "delve", "delving", "tapestry", "revolutionize", "revolutionizing", 
        "next-generation", "next-gen", "innovative", "fast-paced world", 
        "dynamic environment", "results-oriented", "results-driven", 
        "passionate professional", "synergy", "synergies", "spearheaded", 
        "paradigm shift", "thought leader", "rockstar", "ninja", "guru",
        "holistic", "empower", "empowering", "testament", "beacon", "catalyst"
    ]

    SLOP_REPLACEMENTS = {
        "seamlessly": "directly",
        "seamless": "automated",
        "leverage": "use",
        "leveraging": "using",
        "cutting-edge": "modern",
        "robust": "fault-tolerant",
        "next-generation": "scalable",
        "spearheaded": "architected",
        "passionate": "focused",
        "game-changing": "high-impact",
        "delve into": "analyze",
        "synergy": "alignment"
    }

    def __init__(self, rules_path: Path = None):
        self.rules_path = rules_path or settings.ANTI_SLOP_RULES_JSON
        self.prohibited_words = list(self.DEFAULT_PROHIBITED)
        self._load_rules()

    def _load_rules(self):
        if self.rules_path and self.rules_path.exists():
            try:
                with open(self.rules_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "prohibited_buzzwords" in data:
                        self.prohibited_words = list(set(self.prohibited_words + data["prohibited_buzzwords"]))
            except Exception:
                pass

    def evaluate_text(self, text: str) -> Dict[str, any]:
        """
        Scans text and returns a Slop Score (0-100) and detected issues.
        0-20: Distinct & authentic
        21-40: Slightly Generic
        41-60: AI-Looking
        61-80: Heavy Slop
        81-100: Template Collapse
        """
        if not text:
            return {"score": 0, "detected_words": [], "grade": "Distinct"}

        lower_text = text.lower()
        detected = []
        for word in self.prohibited_words:
            pattern = rf"\b{re.escape(word)}\b"
            matches = re.findall(pattern, lower_text)
            if matches:
                detected.extend(matches)

        word_count = max(1, len(text.split()))
        slop_density = (len(detected) / word_count) * 100
        
        # Calculate score (base penalization per buzzword)
        slop_score = min(100.0, len(detected) * 12.0 + slop_density * 8.0)

        if slop_score <= 20:
            grade = "Distinct"
        elif slop_score <= 40:
            grade = "Slightly Generic"
        elif slop_score <= 60:
            grade = "AI-Looking"
        elif slop_score <= 80:
            grade = "Heavy Slop"
        else:
            grade = "Template Collapse"

        return {
            "score": round(slop_score, 1),
            "grade": grade,
            "detected_words": list(set(detected)),
            "word_count": word_count,
            "is_clean": slop_score <= 25.0
        }

    def sanitize_text(self, text: str) -> str:
        """Replaces AI slop terms with concrete engineering words."""
        sanitized = text
        for slop, clean in self.SLOP_REPLACEMENTS.items():
            pattern = re.compile(rf"\b{re.escape(slop)}\b", re.IGNORECASE)
            sanitized = pattern.sub(clean, sanitized)
        return sanitized
