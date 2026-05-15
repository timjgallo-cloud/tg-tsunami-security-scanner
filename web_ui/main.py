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

@app.post("/worker/enrich")
async def worker_enrich(request: Request):
    """Eventarc background worker endpoint triggered when Tsunami finishes uploading results.json."""
    try:
        body = await request.json()
        # Eventarc GCS event body structure
        bucket = body.get("bucket")
        name = body.get("name") # e.g. {execution_id}.json
        
        if not name or not name.endswith(".json") or name.endswith("_enriched.json"):
            return {"status": "ignored"}
            
        execution_id = name.replace(".json", "")
        logger.info(f"[WORKER] Starting background enrichment for execution {execution_id}")
        
        data = await gcp.read_results(name)
        
        enricher = GtiEnricher()
        try:
            enriched_data = await enricher.enrich_vulnerabilities(data)
            # Write back as {execution_id}_enriched.json
            await gcp.write_results(f"{execution_id}_enriched.json", enriched_data)
            logger.info(f"[WORKER] Successfully completed enrichment for {execution_id}")
        finally:
            await enricher.close()
            
        return {"status": "completed", "execution_id": execution_id}
    except Exception as e:
        logger.error(f"[WORKER] Enrichment failed: {e}")
        return {"status": "error", "message": str(e)}

@app.put("/mock-upload/{filename}")
async def mock_upload(filename: str, request: Request):
    """Simulates Tsunami PUT upload to Signed URL in local mock mode."""
    data = await request.json()
    await gcp.write_results(filename, data)
    
    # Simulate Eventarc triggering the worker
    class MockRequest:
        def __init__(self, body):
            self._body = body
        async def json(self):
            return self._body
            
    await worker_enrich(MockRequest({"bucket": gcp.bucket_name, "name": filename}))
    return {"status": "uploaded"}

@app.get("/results/{execution_id}", response_class=HTMLResponse)
async def results(request: Request, execution_id: str):
    """View scan results for a specific execution."""
    try:
        # First check if pre-enriched results exist
        enriched_filename = f"{execution_id}_enriched.json"
        raw_filename = f"{execution_id}.json"
        
        try:
            data = await gcp.read_results(enriched_filename)
            enriched = True
        except FileNotFoundError:
            # If enriched not found, check if raw exists
            data = await gcp.read_results(raw_filename)
            enriched = False
            
        return templates.TemplateResponse("results.html", {
            "request": request, 
            "execution_id": execution_id,
            "data": data,
            "enriched": enriched
        })
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request, 
            "message": f"Results not ready or not found: {e}"
        })

@app.get("/health")
async def health():
    return {"status": "ok"}
