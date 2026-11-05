import json
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.models import JobPosting, TailoredApplication
from app.intelligence.resume_tailor import ResumeTailor
from app.intelligence.outreach_generator import OutreachGenerator
from app.intelligence.pdf_compiler import PDFCompiler

router = APIRouter(prefix="/api/tailor", tags=["Resume Tailoring"])

tailor_service = ResumeTailor()
outreach_service = OutreachGenerator()
pdf_compiler = PDFCompiler()

@router.post("/{job_id}")
async def tailor_application_for_job(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(JobPosting).where(JobPosting.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Parse matched skills from reason JSON if available
    matched_skills = []
    try:
        reason_data = json.loads(job.match_reason)
        matched_skills = reason_data.get("matched_skills", [])
    except Exception:
        pass

    # 1. Tailor Resume (LaTeX + Markdown)
    tailor_res = await tailor_service.tailor_resume(
        job_title=job.title,
        company=job.company,
        description=job.description,
        matched_skills=matched_skills
    )

    # 2. Compile to PDF / Printable HTML with professional naming
    pdf_res = pdf_compiler.compile_resume(
        job_id=job.id,
        company_slug=job.company,
        role_title=job.title,
        latex_content=tailor_res["tailored_tex"]
    )

    # 3. Generate Cold Emails and LinkedIn 4MM Outreach
    outreach_res = outreach_service.generate_outreach(
        job_title=job.title,
        company=job.company,
        job_url=job.url,
        matched_skills=matched_skills
    )

    # 4. Save or Update TailoredApplication record
    app_res = await db.execute(select(TailoredApplication).where(TailoredApplication.job_id == job_id))
    app_record = app_res.scalar_one_or_none()

    if not app_record:
        app_record = TailoredApplication(
            job_id=job.id,
            tailored_resume_tex=tailor_res["tailored_tex"],
            tailored_resume_md=tailor_res["tailored_md"],
            pdf_path=pdf_res.get("pdf_path", ""),
            cold_email_hr=outreach_res["hr_email"]["body"],
            cold_email_hiring_manager=outreach_res["hiring_manager_email"]["body"],
            linkedin_4mm=json.dumps(outreach_res["linkedin_4mm"]),
            slop_score=tailor_res["slop_score"]
        )
        db.add(app_record)
    else:
        app_record.tailored_resume_tex = tailor_res["tailored_tex"]
        app_record.tailored_resume_md = tailor_res["tailored_md"]
        app_record.pdf_path = pdf_res.get("pdf_path", "")
        app_record.cold_email_hr = outreach_res["hr_email"]["body"]
        app_record.cold_email_hiring_manager = outreach_res["hiring_manager_email"]["body"]
        app_record.linkedin_4mm = json.dumps(outreach_res["linkedin_4mm"])
        app_record.slop_score = tailor_res["slop_score"]

    job.status = "tailored"
    await db.commit()

    return {
        "success": True,
        "job_id": job_id,
        "slop_score": tailor_res["slop_score"],
        "slop_grade": tailor_res["slop_grade"],
        "pdf_path": pdf_res.get("pdf_path", ""),
        "has_pdf": pdf_res.get("success", False)
    }

@router.get("/{job_id}/download-pdf")
async def download_pdf(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TailoredApplication).where(TailoredApplication.job_id == job_id))
    app_record = result.scalar_one_or_none()
    if not app_record or not app_record.pdf_path:
        raise HTTPException(status_code=404, detail="Tailored document not found. Run tailor first.")

    pdf_file = Path(app_record.pdf_path)
    if not pdf_file.exists():
        raise HTTPException(status_code=404, detail="File does not exist on disk.")

    media_type = "application/pdf" if pdf_file.suffix == ".pdf" else "text/html"
    return FileResponse(path=str(pdf_file), filename=pdf_file.name, media_type=media_type)

@router.get("/{job_id}/download-tex")
async def download_tex(job_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TailoredApplication).where(TailoredApplication.job_id == job_id))
    app_record = result.scalar_one_or_none()
    if not app_record or not app_record.tailored_resume_tex:
        raise HTTPException(status_code=404, detail="LaTeX resume not found.")

    job_res = await db.execute(select(JobPosting).where(JobPosting.id == job_id))
    job = job_res.scalar_one_or_none()
    filename = pdf_compiler.format_filename_base(company=job.company if job else "Company", role_title=job.title if job else "Role", job_id=job_id)

    return PlainTextResponse(
        content=app_record.tailored_resume_tex,
        media_type="text/x-tex",
        headers={"Content-Disposition": f'attachment; filename="{filename}.tex"'}
    )

