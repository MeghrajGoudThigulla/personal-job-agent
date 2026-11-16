import pytest
from httpx import AsyncClient, ASGITransport
from app.config import settings
from app.core.database import init_db
from app.main import app
from app.intelligence.resume_variants import ResumeVariantManager, VARIANTS_METADATA

AUTH_HEADERS = {"Authorization": "Bearer supersecretpassword123"}


@pytest.fixture(autouse=True)
def configure_test_auth():
    settings.APP_PASSWORD = "supersecretpassword123"
    yield


def test_variants_metadata_coverage():
    expected = {"base", "backend", "ai", "mobile", "fullstack", "frontend", "consulting"}
    assert set(VARIANTS_METADATA.keys()) == expected

    manager = ResumeVariantManager()
    variants = manager.get_all_variants()
    assert len(variants) == 7
    slugs = {v["slug"] for v in variants}
    assert slugs == expected


def test_variant_selection_routing():
    manager = ResumeVariantManager()

    # Mobile / Flutter
    assert manager.select_best_variant("Senior Flutter Developer", "Mobile") == "mobile"
    assert manager.select_best_variant("iOS & Android Engineer", "Engineering") == "mobile"
    assert manager.select_best_variant("Dart Specialist", "") == "mobile"

    # AI / ML / Vision
    assert manager.select_best_variant("AI Engineer", "Machine Learning") == "ai"
    assert manager.select_best_variant("Computer Vision & OCR Developer", "") == "ai"
    assert manager.select_best_variant("Software Engineer", "", matched_skills=["PaddleOCR", "BGE-M3", "onnx"]) == "ai"

    # Consulting / Architecture
    assert manager.select_best_variant("Solutions Architect", "") == "consulting"
    assert manager.select_best_variant("Technology Consultant", "Advisory") == "consulting"
    assert manager.select_best_variant("Principal Architect", "") == "consulting"

    # Frontend
    assert manager.select_best_variant("Frontend Engineer", "") == "frontend"
    assert manager.select_best_variant("React Developer", "Web") == "frontend"
    assert manager.select_best_variant("Next.js Developer", "") == "frontend"

    # Fullstack
    assert manager.select_best_variant("Full Stack Engineer", "") == "fullstack"
    assert manager.select_best_variant("Fullstack Web Developer", "") == "fullstack"

    # Backend
    assert manager.select_best_variant("Backend Engineer", "") == "backend"
    assert manager.select_best_variant("Python API Developer", "") == "backend"
    assert manager.select_best_variant("FastAPI Systems Engineer", "") == "backend"

    # Description routing fallback
    assert manager.select_best_variant("Software Engineer", "", description="We build high-throughput APIs in FastAPI and PostgreSQL") == "backend"
    assert manager.select_best_variant("Software Engineer", "", description="We build cross-platform mobile apps in Flutter and Dart") == "mobile"
    assert manager.select_best_variant("Software Engineer", "", description="We build responsive React and Next.js interfaces") == "fullstack"

    # Default fallback
    assert manager.select_best_variant("Engineer", "") == "base"


def test_all_variants_no_cpp_and_correct_experience():
    manager = ResumeVariantManager()
    expected_experience = (
        r"\textbf{Full Stack Engineer \& Senior AI Developer} \hfill July 2024 -- October 2026"
    )

    for slug in VARIANTS_METADATA.keys():
        tex = manager.get_variant_latex(slug)
        assert len(tex) > 1000, f"Variant {slug} returned empty or tiny LaTeX"

        # Strict constraint 1: No C++
        assert "C++" not in tex, f"Found C++ in variant {slug}!"

        # Strict constraint 2: Experience title and timeline
        assert expected_experience in tex, f"Expected experience line missing in variant {slug}"
        assert r"Threshing Floor Group, Hyderabad \hfill \href{https://tfgroup.ai/en}{tfgroup.ai}" in tex


def test_variant_files_on_disk():
    resumes_dir = settings.DATA_DIR / "resumes"
    assert resumes_dir.exists(), "resumes directory must exist"

    expected_experience = (
        r"\textbf{Full Stack Engineer \& Senior AI Developer} \hfill July 2024 -- October 2026"
    )

    for slug in ["base", "backend", "ai", "mobile", "fullstack", "frontend", "consulting"]:
        p = resumes_dir / f"resume_{slug}.tex"
        assert p.exists(), f"Resume file {p} does not exist"
        content = p.read_text(encoding="utf-8")
        assert "C++" not in content, f"C++ found in file {p}"
        assert expected_experience in content, f"Experience header missing in file {p}"


@pytest.mark.asyncio
async def test_variants_api_endpoints():
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # GET /api/tailor/variants
        res = await ac.get("/api/tailor/variants", headers=AUTH_HEADERS)
        assert res.status_code == 200
        variants = res.json()
        assert len(variants) == 7

        # GET /api/tailor/variants/backend/tex
        res_tex = await ac.get("/api/tailor/variants/backend/tex", headers=AUTH_HEADERS)
        assert res_tex.status_code == 200
        tex_text = res_tex.text
        assert "C++" not in tex_text
        assert "Full Stack Engineer \\& Senior AI Developer" in tex_text
        assert "Content-Disposition" in res_tex.headers

        # GET /api/tailor/variants/mobile/pdf
        res_pdf = await ac.get("/api/tailor/variants/mobile/pdf", headers=AUTH_HEADERS)
        assert res_pdf.status_code == 200
        assert len(res_pdf.content) > 0
