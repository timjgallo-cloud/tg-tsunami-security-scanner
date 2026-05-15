import os
import logging
import uuid
import json
import asyncio

logger = logging.getLogger(__name__)

# Temporary mock data storage for local testing
_MOCK_STORAGE = {}

class CloudPlatform:
    def __init__(self):
        self.local_mode = os.environ.get("LOCAL_MODE", "false").lower() == "true"
        self.project_id = os.environ.get("PROJECT_ID")
        self.region = os.environ.get("REGION", "us-central1")
        self.job_name = os.environ.get("SCANNER_JOB_NAME")
        self.bucket_name = os.environ.get("GCS_BUCKET")
        
        if not self.local_mode:
            from google.cloud import run_v2
            from google.cloud import storage
            self.run_client = run_v2.JobsClient()
            self.formatted_job_name = f"projects/{self.project_id}/locations/{self.region}/jobs/{self.job_name}" if self.project_id and self.job_name else None
            self.storage_client = storage.Client()
        else:
            logger.info("Running in LOCAL_MODE. Using mock GCP services.")

    async def run_job(self, target: str) -> str:
        """Triggers the Cloud Run Job."""
        execution_id = str(uuid.uuid4())
        
        if self.local_mode:
            logger.info(f"[MOCK] Triggering job for target {target} with ID {execution_id}")
            # Simulate a scan duration and result creation in background
            mock_result = {
                "scanStatus": "COMPLETED",
                "scanFindings": [
                    {
                        "vulnerability": {
                             "cveId": "CVE-2023-1234",
                             "title": "Mock Vulnerability in Test",
                             "description": "This is a simulated vulnerability found in local mode.",
                             "rating": "HIGH"
                        }
                    },
                    {
                        "vulnerability": {
                             "cveId": "CVE-2024-5678",
                             "title": "Another Mock Issue",
                             "description": "Simulated low risk issue.",
                             "rating": "LOW"
                        }
                    }
                ]
            }
            _MOCK_STORAGE[f"{execution_id}.json"] = json.dumps(mock_result)
            return execution_id

        if not self.formatted_job_name:
            raise ValueError("Cloud Run configuration missing (PROJECT_ID, REGION, SCANNER_JOB_NAME)")
            
        # Generate Signed URL for Tsunami to upload results
        signed_url = await self.generate_signed_url(f"{execution_id}.json")
        
        from google.cloud import run_v2
        overrides = run_v2.RunJobRequest.Overrides(
            container_overrides=[
                run_v2.RunJobRequest.Overrides.ContainerOverride(
                    env=[
                        run_v2.EnvVar(name="TARGET", value=target),
                        run_v2.EnvVar(name="EXECUTION_ID", value=execution_id),
                        run_v2.EnvVar(name="GCS_BUCKET", value=self.bucket_name),
                        run_v2.EnvVar(name="UPLOAD_URL", value=signed_url),
                    ]
                )
            ]
        )

        request = run_v2.RunJobRequest(
            name=self.formatted_job_name,
            overrides=overrides
        )

        operation = self.run_client.run_job(request=request)
        logger.info(f"Job triggered for target {target}, Execution ID: {execution_id}")
        return execution_id

    async def generate_signed_url(self, filename: str) -> str:
        """Generates a GCS Signed Upload URL."""
        if self.local_mode:
            logger.info(f"[MOCK] Generating signed URL for {filename}")
            return f"http://127.0.0.1:8080/mock-upload/{filename}"
            
        import datetime
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(filename)
        
        # Generate Signed URL valid for 2 hours
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(hours=2),
            method="PUT",
            content_type="application/json"
        )
        return signed_url

    async def read_results(self, filename: str) -> dict:
        """Reads JSON results from GCS."""
        if self.local_mode:
            logger.info(f"[MOCK] Reading {filename} from mock storage.")
            content = _MOCK_STORAGE.get(filename)
            if not content:
                raise FileNotFoundError(f"Result file {filename} not found (Mock).")
            return json.loads(content)

        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(filename)
        
        if not blob.exists():
            raise FileNotFoundError(f"Result file {filename} not found.")
            
        content = blob.download_as_text()
        return json.loads(content)

    async def write_results(self, filename: str, data: dict):
        """Writes JSON results to GCS (used by background enrichment worker)."""
        if self.local_mode:
            logger.info(f"[MOCK] Writing {filename} to mock storage.")
            _MOCK_STORAGE[filename] = json.dumps(data)
            return
            
        bucket = self.storage_client.bucket(self.bucket_name)
        blob = bucket.blob(filename)
        blob.upload_from_string(json.dumps(data), content_type="application/json")
