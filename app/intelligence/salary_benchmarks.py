"""
Salary Benchmarking and Compensation Intelligence Module.
Extracts stated compensation from job postings and infers market benchmark ranges
for Indian tech hubs (Bangalore, Hyderabad, Pune, Gurgaon) and Global Remote roles.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional


class SalaryBenchmarker:
    """
    Extracts and benchmarks compensation for tech roles.
    """

    # Indian Tech Market Compensation Bands (INR Lakhs Per Annum)
    BASE_BANDS_LPA: Dict[str, Dict[str, str]] = {
        "senior": {"min": 24, "max": 42},
        "lead": {"min": 40, "max": 65},
        "staff": {"min": 50, "max": 85},
        "mid": {"min": 14, "max": 24},
        "junior": {"min": 7, "max": 14},
    }

    # Global Remote Compensation Bands (USD)
    GLOBAL_REMOTE_BANDS_USD: Dict[str, Dict[str, str]] = {
        "senior": {"min": 75000, "max": 135000},
        "lead": {"min": 110000, "max": 180000},
        "staff": {"min": 140000, "max": 220000},
        "mid": {"min": 50000, "max": 85000},
        "junior": {"min": 35000, "max": 55000},
    }

    def extract_stated_salary(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extracts explicit salary mentions from job descriptions or snippets.
        """
        if not text:
            return None

        # 1. LPA Format: e.g. "18 - 30 LPA" or "25-35 Lakhs"
        lpa_match = re.search(
            r"(?:₹|inr|rs\.?)?\s*(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakhs?|lac|l\b)",
            text,
            re.IGNORECASE
        )
        if lpa_match:
            min_val = float(lpa_match.group(1))
            max_val = float(lpa_match.group(2))
            return {
                "raw_text": lpa_match.group(0).strip(),
                "min": min_val,
                "max": max_val,
                "currency": "INR",
                "unit": "LPA",
                "formatted": f"₹{min_val:.1f} - ₹{max_val:.1f} LPA"
            }

        # 2. USD K Format: e.g. "$120k - $160k" or "100K - 140K USD"
        usd_k_match = re.search(
            r"\$\s*(\d{2,3})\s*k\s*(?:-|to)\s*\$?\s*(\d{2,3})\s*k",
            text,
            re.IGNORECASE
        )
        if usd_k_match:
            min_k = int(usd_k_match.group(1)) * 1000
            max_k = int(usd_k_match.group(2)) * 1000
            return {
                "raw_text": usd_k_match.group(0).strip(),
                "min": min_k,
                "max": max_k,
                "currency": "USD",
                "unit": "Annual",
                "formatted": f"${min_k:,} - ${max_k:,} USD"
            }

        # 3. Numeric INR Format: e.g. "₹1,500,000 - ₹2,500,000"
        inr_num_match = re.search(
            r"₹\s*([0-9,]{6,10})\s*(?:-|to)\s*₹?\s*([0-9,]{6,10})",
            text
        )
        if inr_num_match:
            v1 = int(inr_num_match.group(1).replace(",", ""))
            v2 = int(inr_num_match.group(2).replace(",", ""))
            min_lpa = round(v1 / 100000, 1)
            max_lpa = round(v2 / 100000, 1)
            return {
                "raw_text": inr_num_match.group(0).strip(),
                "min": min_lpa,
                "max": max_lpa,
                "currency": "INR",
                "unit": "LPA",
                "formatted": f"₹{min_lpa} - ₹{max_lpa} LPA"
            }

        return None

    def determine_seniority(self, title: str, description: str = "") -> str:
        """
        Determines the seniority tier of the role.
        """
        combined = f"{title} {description}".lower()

        if any(w in combined for w in ["staff", "principal", "director", "head of"]):
            return "staff"
        elif any(w in combined for w in ["lead", "architect", "engineering manager"]):
            return "lead"
        elif any(w in combined for w in ["senior", "sr.", "sde-2", "sde 2", "sde ii", "sde2", "engineer ii", "level 2"]):
            return "senior"
        elif any(w in combined for w in ["junior", "jr.", "entry", "intern", "associate"]):
            return "junior"
        else:
            return "mid"

    def benchmark(
        self,
        job_title: str,
        company: str = "",
        location: str = "",
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Produces compensation intelligence and negotiation benchmarks.
        """
        combined_text = f"{job_title} {company} {description}"
        stated = self.extract_stated_salary(combined_text)
        seniority = self.determine_seniority(job_title, description)

        is_global_remote = any(
            w in location.lower() or w in description.lower()
            for w in ["worldwide", "global remote", "anywhere", "us remote", "latam/apac"]
        )

        inr_band = self.BASE_BANDS_LPA.get(seniority, self.BASE_BANDS_LPA["mid"])
        usd_band = self.GLOBAL_REMOTE_BANDS_USD.get(seniority, self.GLOBAL_REMOTE_BANDS_USD["mid"])

        seniority_labels = {
            "junior": "Entry Level / Junior (1-2 YOE)",
            "mid": "Mid-Level Engineer (2-4 YOE)",
            "senior": "Senior Engineer / SDE II (3-6 YOE)",
            "lead": "Tech Lead / Architect (5-9 YOE)",
            "staff": "Staff / Principal Engineer (8+ YOE)",
        }

        negotiation_tips = {
            "junior": "Focus on high learning velocity, clean code standards, and production ownership.",
            "mid": "Emphasize proven end-to-end API delivery, sub-100ms database performance, and zero-downtime migrations.",
            "senior": "Anchor around architectural leadership: designing multi-service systems, concurrency bottlenecks, and mentoring.",
            "lead": "Highlight technical strategy, system resilience, cross-functional alignment, and trade-off decisions.",
            "staff": "Demonstrate organizational leverage, platform scalability, and technology roadmap execution.",
        }

        return {
            "has_stated_salary": bool(stated),
            "stated_salary": stated["formatted"] if stated else None,
            "stated_salary_details": stated,
            "seniority_tier": seniority_labels.get(seniority, "Mid-Level"),
            "benchmark_inr_lpa": f"₹{inr_band['min']} - ₹{inr_band['max']} LPA",
            "benchmark_usd_annual": f"${usd_band['min']:,} - ${usd_band['max']:,} USD",
            "is_global_remote": is_global_remote,
            "primary_currency": "USD" if (is_global_remote and stated and stated.get("currency") == "USD") else "INR",
            "negotiation_tip": negotiation_tips.get(seniority, negotiation_tips["mid"]),
        }
