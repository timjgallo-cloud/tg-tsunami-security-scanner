
import os
import json
import logging
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from gcp import CloudPlatform
from enrichment import GtiEnricher

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
gcp = CloudPlatform()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the home page."""
    return templates.TemplateResponse("index.html", {"request": request, "jobs": []})

@app.post("/scan")
async def scan(request: Request, target: str = Form(...)):
    """Trigger a new scan job."""
    try:
        execution_id = await gcp.run_job(target)
        return templates.TemplateResponse("success.html", {
            "request": request, 
            "target": target, 
            "execution_id": execution_id
        })
    except Exception as e:
        logger.error(f"Failed to start scan: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request, 
            "message": str(e)
        })

@app.get("/results/{execution_id}", response_class=HTMLResponse)
async def results(request: Request, execution_id: str):
    """View scan results for a specific execution."""
    try:
        # Expected GCS filename format: {execution_id}.json
        # Note: The scanner needs to know this ID or we use a timestamp. 
        # For simplicity, we might list files in the bucket or rely on a known naming convention.
        # In this plan, let's assume the scanner names the file based on the execution ID passed as env var
        # or we just list the latest for the target.
        
        # Actually, best practice: Pass EXECUTION_ID env var to the job.
        data = await gcp.read_results(f"{execution_id}.json")
        
        
        # Enrichment
        enricher = GtiEnricher()
        try:
             data = await enricher.enrich_vulnerabilities(data)
        finally:
             await enricher.close()
        
        return templates.TemplateResponse("results.html", {
            "request": request, 
            "execution_id": execution_id,
            "data": data,
            "enriched": True
        })
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request, 
            "message": f"Results not ready or not found: {e}"
        })

@app.get("/health")
async def health():
    return {"status": "ok"}
