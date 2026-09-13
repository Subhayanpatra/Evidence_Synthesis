from __future__ import annotations

import io
import json
import math
import os
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from agents.paper_agent import process_paper
from agents.query_normalization_agent import normalize_query
from agents.sap_agent import sap_agent
from pubmed.pmc_filter import get_required_pmc_papers
from pubmed.query_builder import build_query


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
STATIC_DIR = WEB_DIR / "static"
MAX_WORKERS = max(1, int(os.getenv("AI_EXTRACT_MAX_WORKERS", "2")))
PAPER_PROCESS_MAX_WORKERS = max(
    1,
    min(5, int(os.getenv("PAPER_PROCESS_MAX_WORKERS", "3"))),
)

app = FastAPI(
    title="Medical Research AI Platform",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url=None,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="ai-extract")
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


class SearchRequest(BaseModel):
    medical_query: str = Field(min_length=1, max_length=5000)
    normalized_query: str = Field(min_length=1, max_length=5000)
    query_confirmed: bool
    normalization_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    normalization_query_style: Literal["keyword_query", "detailed_query"] = (
        "keyword_query"
    )
    paper_count: int = Field(default=30, ge=1, le=200)
    use_year_filter: bool = False
    start_year: int | None = Field(default=None, ge=1900, le=2100)
    end_year: int | None = Field(default=None, ge=1900, le=2100)
    run_agents: bool = False
    max_agent_papers: int = Field(default=5)
    slr_handling: Literal["include", "exclude"] = "include"
    generate_sap: bool = False

    @model_validator(mode="after")
    def validate_years(self) -> "SearchRequest":
        self.medical_query = " ".join(self.medical_query.split())
        self.normalized_query = " ".join(self.normalized_query.split())
        if not self.query_confirmed:
            raise ValueError("The normalized query must be confirmed before searching.")
        if self.run_agents:
            if not 1 <= self.max_agent_papers <= 200:
                raise ValueError(
                    "The number of papers to analyze must be between 1 and 200."
                )
        else:
            self.max_agent_papers = 5
        if self.use_year_filter:
            if self.start_year is None or self.end_year is None:
                raise ValueError("Both start year and end year are required.")
            if self.start_year > self.end_year:
                raise ValueError("Start year must be less than or equal to end year.")
        else:
            self.start_year = None
            self.end_year = None
        return self


class NormalizeRequest(BaseModel):
    medical_query: str = Field(min_length=1, max_length=5000)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_job(request: SearchRequest) -> str:
    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "stage": "queued",
            "progress": 0,
            "message": "Search queued.",
            "created_at": _now(),
            "updated_at": _now(),
            "request": request.model_dump(),
            "result": None,
            "error": "",
        }
    return job_id


def _update_job(job_id: str, **updates: Any) -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        job.update(updates)
        job["updated_at"] = _now()


def _job_snapshot(job_id: str) -> dict[str, Any] | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _count_codes(papers: list[dict[str, Any]]) -> int:
    fields = ("ICD_9_CM", "ICD_10_CM", "ICD_10_PCS", "CPT", "HCPCS", "NDC")
    codes = set()
    for paper in papers:
        for field in fields:
            value = str(paper.get(field, "") or "")
            for code in value.split(";"):
                code = code.strip()
                if code:
                    codes.add(f"{field}:{code}")
    return len(codes)


def _count_countries(papers: list[dict[str, Any]]) -> int:
    countries = set()
    for paper in papers:
        for country in str(paper.get("Country", "") or "").split(";"):
            country = country.strip()
            if country:
                countries.add(country.casefold())
    return len(countries)


def _run_search_job(job_id: str, request: SearchRequest) -> None:
    try:
        _update_job(
            job_id,
            status="running",
            stage="searching",
            progress=10,
            message="Normalizing the medical research query…",
        )
        normalization = {
            "input": request.medical_query,
            "original_user_query": request.medical_query,
            "normalized_query": request.normalized_query,
            "is_valid_medical_query": True,
            "confidence": request.normalization_confidence,
            "query_style": request.normalization_query_style,
            "query_confirmed": True,
            "normalization_method": "User confirmed",
        }
        normalized_query = request.normalized_query
        pubmed_query = build_query(
            normalized_query,
            start_year=request.start_year,
            end_year=request.end_year,
        )
        _update_job(
            job_id,
            stage="searching",
            progress=15,
            message=f"Searching Europe PMC for {request.paper_count} open-access papers…",
        )
        candidate_limit = min(request.paper_count * 5, 1000)
        candidates = get_required_pmc_papers(
            disease=normalized_query,
            required_papers=candidate_limit,
            start_year=request.start_year,
            end_year=request.end_year,
        )

        papers = []
        candidates_assessed = 0
        not_relevant_count = 0
        excluded_slr_count = 0

        if candidates:
            # Baseline paper work is independent and I/O-heavy. Process small
            # ordered batches concurrently, then consume results in Europe PMC
            # relevance order. Advanced extraction keeps its existing tighter
            # per-paper concurrency so API traffic remains bounded.
            baseline_parallel = not request.run_agents and not request.generate_sap
            batch_size = PAPER_PROCESS_MAX_WORKERS if baseline_parallel else 1

            for batch_start in range(0, len(candidates), batch_size):
                batch = candidates[batch_start:batch_start + batch_size]
                run_extended_by_paper = [
                    request.generate_sap or (
                        request.run_agents and len(papers) < request.max_agent_papers
                    )
                    for _paper in batch
                ]

                def process_candidate(item):
                    paper, run_extended_agents = item
                    try:
                        return process_paper(
                            str(paper.get("PMCID", "")),
                            title=str(paper.get("Title", "")),
                            query=str(normalization.get("original_user_query", "")),
                            include_supplementary=True,
                            run_extended_agents=run_extended_agents,
                            exclude_slr=request.slr_handling == "exclude",
                        )
                    except Exception as exc:
                        return {"Agent_Error": str(exc)}

                work = list(zip(batch, run_extended_by_paper))
                if baseline_parallel and len(work) > 1:
                    with ThreadPoolExecutor(
                        max_workers=PAPER_PROCESS_MAX_WORKERS,
                        thread_name_prefix="paper-process",
                    ) as paper_executor:
                        batch_results = list(paper_executor.map(process_candidate, work))
                else:
                    batch_results = [process_candidate(item) for item in work]

                for offset, (paper, agent_result) in enumerate(zip(batch, batch_results)):
                    index = batch_start + offset
                    run_extended_agents = run_extended_by_paper[offset]
                    progress = 25 + round((index / max(1, len(candidates))) * 65)
                    processing_label = (
                        "Running advanced extraction from SLR through outcomes"
                        if run_extended_agents
                        else "Checking relevance before supplementary extraction"
                    )
                    _update_job(
                        job_id,
                        stage="extracting",
                        progress=progress,
                        message=(
                            f"{processing_label} {index + 1}/{len(candidates)}: "
                            f"{paper.get('PMCID', '')}"
                        ),
                    )
                    paper.update(agent_result)
                    candidates_assessed += 1

                    if paper.get("Relevant") is not True:
                        not_relevant_count += 1
                        continue
                    if request.slr_handling == "exclude" and paper.get("Is_SLR") is True:
                        excluded_slr_count += 1
                        continue

                    papers.append(paper)
                    if len(papers) >= request.paper_count:
                        break

                if len(papers) >= request.paper_count:
                    break

        safe_papers = [_json_safe(paper) for paper in papers]
        sap = None
        if request.generate_sap:
            _update_job(
                job_id,
                stage="generating_sap",
                progress=95,
                message=(
                    f"Combining extracted information from {len(safe_papers)} "
                    "relevant papers into one draft SAP."
                ),
            )
            sap = _json_safe(
                sap_agent(
                    normalized_query,
                    safe_papers,
                    requested=request.paper_count,
                    returned=len(safe_papers),
                )
            )
        result = {
            "normalization": _json_safe(normalization),
            "pubmed_query": pubmed_query,
            "requested": request.paper_count,
            "returned": len(safe_papers),
            "candidates_assessed": candidates_assessed,
            "not_relevant": not_relevant_count,
            "excluded_slr": excluded_slr_count,
            "papers": safe_papers,
            "sap_requested": request.generate_sap,
            "sap": sap,
            "metrics": {
                "total_papers": len(safe_papers),
                "pmc_articles": sum(bool(paper.get("PMCID")) for paper in safe_papers),
                "countries": _count_countries(safe_papers),
                "medical_codes": _count_codes(safe_papers),
                "relevant_papers": sum(
                    paper.get("Relevant") is True for paper in safe_papers
                ),
            },
        }
        _update_job(
            job_id,
            status="complete",
            stage="complete",
            progress=100,
            message=(
                f"Completed. Found {len(safe_papers)} relevant PMC papers "
                f"after assessing {candidates_assessed} candidates."
            ),
            result=result,
        )
    except Exception as exc:
        _update_job(
            job_id,
            status="failed",
            stage="failed",
            progress=100,
            message="The search could not be completed.",
            error=str(exc),
        )


def _csv_cell(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple, set)):
        value = json.dumps(_json_safe(value), ensure_ascii=False)
    if value is None:
        return ""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/search", status_code=202)
def create_search(request: SearchRequest) -> dict[str, str]:
    job_id = _new_job(request)
    _executor.submit(_run_search_job, job_id, request)
    return {"job_id": job_id, "status": "queued"}


@app.post("/api/normalize")
def normalize_search_query(request: NormalizeRequest) -> dict[str, Any]:
    normalization = normalize_query(request.medical_query)
    if normalization.get("normalization_method") == "Error":
        raise HTTPException(
            status_code=502,
            detail=f"Query normalization failed: {normalization.get('error', 'Unknown error')}",
        )
    if not normalization.get("is_valid_medical_query"):
        raise HTTPException(
            status_code=422,
            detail=f'"{request.medical_query}" was not recognized as a valid medical query.',
        )
    return _json_safe(normalization)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = _job_snapshot(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Search job was not found.")
    return job


@app.get("/api/jobs/{job_id}/download")
def download_results(job_id: str) -> StreamingResponse:
    job = _job_snapshot(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Search job was not found.")
    if job.get("status") != "complete" or not job.get("result"):
        raise HTTPException(status_code=409, detail="Search results are not ready.")

    papers = job["result"].get("papers", [])
    dataframe = pd.DataFrame(
        [{key: _csv_cell(value) for key, value in paper.items()} for paper in papers]
    )
    buffer = io.StringIO()
    dataframe.to_csv(buffer, index=False)
    content = buffer.getvalue().encode("utf-8-sig")
    query = job["result"]["normalization"].get("normalized_query", "pmc_papers")
    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", str(query)).strip("_")[:80]
    headers = {
        "Content-Disposition": f'attachment; filename="{filename or "pmc_papers"}.csv"'
    }
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )


@app.get("/api/jobs/{job_id}/sap/download")
def download_sap(job_id: str) -> StreamingResponse:
    job = _job_snapshot(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Search job was not found.")
    if job.get("status") != "complete" or not job.get("result"):
        raise HTTPException(status_code=409, detail="Search results are not ready.")
    sap = job["result"].get("sap")
    if not sap:
        raise HTTPException(status_code=404, detail="A SAP was not requested for this search.")
    content = json.dumps(sap, ensure_ascii=False, indent=2).encode("utf-8")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="statistical_analysis_plan.json"'},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("AI_EXTRACT_HOST", "127.0.0.1"),
        port=int(os.getenv("AI_EXTRACT_PORT", "8000")),
        reload=False,
    )
