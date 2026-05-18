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
    try:
        jobs = await gcp.list_scans()
    except Exception as e:
        logger.error(f"Failed to list scans: {e}")
        jobs = []
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "jobs": jobs,
        "active_tab": "dashboard"
    })

@app.post("/scan")
async def scan(request: Request, target: str = Form(...)):
    """Trigger a new scan job."""
    try:
        execution_id = await gcp.run_job(target)
        return templates.TemplateResponse("success.html", {
            "request": request, 
            "target": target, 
            "execution_id": execution_id,
            "active_tab": "dashboard"
        })
    except Exception as e:
        logger.error(f"Failed to start scan: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request, 
            "message": str(e),
            "active_tab": "dashboard"
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
    """View scan results or status for a specific execution."""
    try:
        # Get scan execution metadata from Cloud Run
        try:
            scan_info = await gcp.get_scan(execution_id)
            status = scan_info.get("status", "Unknown")
        except Exception as e:
            logger.warning(f"Could not fetch execution metadata for {execution_id}: {e}")
            scan_info = {"id": execution_id, "target": "Unknown Target", "status": "Unknown", "create_time": "Just now"}
            status = "Unknown"

        # Check if results exist in GCS
        enriched_filename = f"{execution_id}_enriched.json"
        raw_filename = f"{execution_id}.json"
        
        try:
            data = await gcp.read_results(enriched_filename)
            enriched = True
            return templates.TemplateResponse("results.html", {
                "request": request, 
                "execution_id": execution_id,
                "data": data,
                "enriched": enriched,
                "active_tab": "dashboard"
            })
        except FileNotFoundError:
            try:
                data = await gcp.read_results(raw_filename)
                enriched = False
                return templates.TemplateResponse("results.html", {
                    "request": request, 
                    "execution_id": execution_id,
                    "data": data,
                    "enriched": enriched,
                    "active_tab": "dashboard"
                })
            except FileNotFoundError:
                # Results file does not exist in GCS yet
                if status == "Running" or status == "Unknown":
                    # Generate live GCP Console log link for Cloud Run execution
                    gcp_console_url = None
                    if not gcp.local_mode and gcp.project_id and scan_info.get("name"):
                        gcp_console_url = f"https://console.cloud.google.com/run/jobs/executions/details/{gcp.region}/{scan_info['name']}?project={gcp.project_id}"
                    
                    return templates.TemplateResponse("scan_progress.html", {
                        "request": request,
                        "execution_id": execution_id,
                        "scan": scan_info,
                        "gcp_console_url": gcp_console_url,
                        "active_tab": "dashboard"
                    })
                elif status == "Failed":
                    return templates.TemplateResponse("error.html", {
                        "request": request,
                        "message": "The vulnerability assessment job failed to execute. Please check the Cloud Run Console logs.",
                        "active_tab": "dashboard"
                    })
                else:
                    # Fallback loader template
                    return templates.TemplateResponse("scan_progress.html", {
                        "request": request,
                        "execution_id": execution_id,
                        "scan": scan_info,
                        "active_tab": "dashboard"
                    })
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request, 
            "message": str(e),
            "active_tab": "dashboard"
        })

@app.get("/projects", response_class=HTMLResponse)
async def projects(request: Request):
    """Render the Projects placeholder page."""
    return templates.TemplateResponse("placeholder.html", {
        "request": request,
        "active_tab": "projects",
        "title": "Projects",
        "description": "Organize your targets and scanning campaigns into distinct, isolated environments for better team collaboration."
    })

@app.get("/collections", response_class=HTMLResponse)
async def collections(request: Request):
    """Render the Collections placeholder page."""
    return templates.TemplateResponse("placeholder.html", {
        "request": request,
        "active_tab": "collections",
        "title": "Collections",
        "description": "Group endpoints, API definitions, and subnets into reusable host lists for batch Tsunami scanning."
    })

@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    """Render the Settings placeholder page."""
    return templates.TemplateResponse("placeholder.html", {
        "request": request,
        "active_tab": "settings",
        "title": "Settings",
        "description": "Manage engine keys, API rate limiting policies, custom plugin weights, and notification webhooks."
    })

@app.get("/health")
async def health():
    return {"status": "ok"}
