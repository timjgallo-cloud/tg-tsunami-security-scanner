import os
import logging
import uuid
import json
import asyncio

logger = logging.getLogger(__name__)

# Temporary mock data storage for local testing
_MOCK_EXECUTIONS = [
    {
        "id": "mock-execution-1024",
        "name": "tsunami-scanner-a1b2c",
        "target": "192.168.1.1",
        "status": "Completed",
        "status_class": "status-completed",
        "create_time": "2026-05-18 12:00:00 UTC",
        "risk": "High"
    },
    {
        "id": "mock-execution-1025",
        "name": "tsunami-scanner-d3e4f",
        "target": "10.128.0.5",
        "status": "Completed",
        "status_class": "status-completed",
        "create_time": "2026-05-18 14:30:00 UTC",
        "risk": "None"
    }
]

_MOCK_STORAGE = {
    "mock-execution-1024.json": json.dumps({
        "scanStatus": "COMPLETED",
        "scanFindings": [
            {
                "vulnerability": {
                     "cveId": "CVE-2023-1234",
                     "title": "Mock Vulnerability in Test",
                     "description": "This is a simulated vulnerability found in local mode.",
                     "rating": "HIGH"
                }
            }
        ]
    }),
    "mock-execution-1025.json": json.dumps({
        "scanStatus": "COMPLETED",
        "scanFindings": []
    })
}

class CloudPlatform:
    def __init__(self):
        self.local_mode = os.environ.get("LOCAL_MODE", "false").lower() == "true"
        self.project_id = os.environ.get("PROJECT_ID")
        self.region = os.environ.get("REGION", "us-central1")
        self.job_name = os.environ.get("SCANNER_JOB_NAME")
        self.bucket_name = os.environ.get("GCS_BUCKET")
        self.service_account_email = os.environ.get("SERVICE_ACCOUNT_EMAIL")
        self.pubsub_topic = os.environ.get("PUBSUB_TOPIC")
        
        if not self.local_mode:
            import google.auth
            from google.auth import impersonated_credentials
            from google.cloud import run_v2
            from google.cloud import storage
            
            self.run_client = run_v2.JobsClient()
            self.execution_client = run_v2.ExecutionsClient()
            self.formatted_job_name = f"projects/{self.project_id}/locations/{self.region}/jobs/{self.job_name}" if self.project_id and self.job_name else None
            
            # Initialize GCS client with impersonated credentials to support keyless signing
            base_credentials, project = google.auth.default()
            if self.service_account_email:
                logger.info(f"Impersonating Web UI Service Account: {self.service_account_email} for keyless GCS URL signing")
                self.storage_credentials = impersonated_credentials.Credentials(
                    source_credentials=base_credentials,
                    target_principal=self.service_account_email,
                    target_scopes=["https://www.googleapis.com/auth/devstorage.read_write"],
                    lifetime=3600
                )
                self.storage_client = storage.Client(credentials=self.storage_credentials, project=self.project_id)
            else:
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
            
            # Append to mock executions list for Recent Activity
            _MOCK_EXECUTIONS.insert(0, {
                "id": execution_id,
                "name": f"tsunami-scanner-{execution_id[:8]}",
                "target": target,
                "status": "Completed",
                "status_class": "status-completed",
                "create_time": "Just now",
                "risk": "High"
            })
            return execution_id

        if not self.formatted_job_name:
            raise ValueError("Cloud Run configuration missing (PROJECT_ID, REGION, SCANNER_JOB_NAME)")
            
        # Generate Signed URL for Tsunami to upload results
        signed_url = await self.generate_signed_url(f"{execution_id}.json")
        
        from google.cloud import run_v2
        env_vars = [
            run_v2.EnvVar(name="TARGET", value=target),
            run_v2.EnvVar(name="EXECUTION_ID", value=execution_id),
            run_v2.EnvVar(name="GCS_BUCKET", value=self.bucket_name),
            run_v2.EnvVar(name="UPLOAD_URL", value=signed_url),
        ]
        if self.pubsub_topic:
            env_vars.append(run_v2.EnvVar(name="PUBSUB_TOPIC", value=self.pubsub_topic))

        overrides = run_v2.RunJobRequest.Overrides(
            container_overrides=[
                run_v2.RunJobRequest.Overrides.ContainerOverride(
                    env=env_vars
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
        
        # Generate Signed URL valid for 2 hours using IAM Credentials API (Sign Blob)
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(hours=2),
            method="PUT",
            content_type="application/json",
            service_account_email=self.service_account_email
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

    async def list_scans(self) -> list:
        """Lists the recent scan executions."""
        if self.local_mode:
            logger.info("[MOCK] Listing executions.")
            return _MOCK_EXECUTIONS

        if not self.formatted_job_name:
            return []

        from google.cloud import run_v2
        
        try:
            # Call blocking list_executions in executor to avoid blocking event loop
            loop = asyncio.get_running_loop()
            def fetch():
                request = run_v2.ListExecutionsRequest(parent=self.formatted_job_name)
                return list(self.execution_client.list_executions(request=request))
            
            executions = await loop.run_in_executor(None, fetch)
        except Exception as e:
            logger.error(f"Failed to list Cloud Run executions: {e}")
            return []

        jobs = []
        for exe in executions:
            # Get execution ID (the last part of execution name)
            exe_name = exe.name.split("/")[-1]
            
            # Extract target and execution_id from container env overrides
            target = "Unknown"
            execution_id = None
            
            try:
                if exe.template and exe.template.containers:
                    for env_var in exe.template.containers[0].env:
                        if env_var.name == "TARGET":
                            target = env_var.value
                        elif env_var.name == "EXECUTION_ID":
                            execution_id = env_var.value
            except Exception as e:
                logger.warning(f"Failed to parse container env for execution {exe_name}: {e}")

            # If no execution_id in env, default to the execution name suffix
            if not execution_id:
                execution_id = exe_name

            # Determine status
            status = "Running"
            status_class = "status-running"
            
            if exe.completion_time:
                if exe.failed_count > 0:
                    status = "Failed"
                    status_class = "status-failed"
                else:
                    status = "Completed"
                    status_class = "status-completed"

            # Determine risk/vulnerabilities by checking GCS results file
            risk = "Pending"
            if status == "Completed":
                risk = "None"
                # Check if enriched or raw result exists in GCS
                try:
                    enriched_filename = f"{execution_id}_enriched.json"
                    raw_filename = f"{execution_id}.json"
                    
                    bucket = self.storage_client.bucket(self.bucket_name)
                    blob = bucket.blob(enriched_filename)
                    if blob.exists():
                        try:
                            content = blob.download_as_text()
                            data = json.loads(content)
                            risk = self._determine_risk_level(data)
                        except Exception:
                            risk = "Error"
                    else:
                        blob_raw = bucket.blob(raw_filename)
                        if blob_raw.exists():
                            try:
                                content = blob_raw.download_as_text()
                                data = json.loads(content)
                                risk = self._determine_risk_level(data)
                            except Exception:
                                risk = "Error"
                except Exception as e:
                    logger.warning(f"Failed to check GCS results for risk level of {execution_id}: {e}")
                    risk = "Unknown"
            elif status == "Failed":
                risk = "N/A"

            # Format create time
            create_time_str = ""
            if exe.create_time:
                create_time_str = exe.create_time.strftime("%Y-%m-%d %H:%M:%S UTC")

            jobs.append({
                "id": execution_id,
                "name": exe_name,
                "target": target,
                "status": status,
                "status_class": status_class,
                "create_time": create_time_str,
                "risk": risk
            })
            
        return jobs

    def _determine_risk_level(self, data: dict) -> str:
        """Determines the risk level based on the scan results data."""
        findings = data.get("scanFindings", [])
        if not findings:
            return "None"
            
        ratings = [f.get("vulnerability", {}).get("rating", "UNKNOWN").upper() for f in findings]
        if "CRITICAL" in ratings:
            return "Critical"
        elif "HIGH" in ratings:
            return "High"
        elif "MEDIUM" in ratings:
            return "Medium"
        elif "LOW" in ratings:
            return "Low"
        return "Info"

    async def get_scan(self, execution_id: str) -> dict:
        """Gets details of a specific scan execution by its execution_id."""
        if self.local_mode:
            for exe in _MOCK_EXECUTIONS:
                if exe["id"] == execution_id:
                    return exe
            raise FileNotFoundError(f"Scan {execution_id} not found.")

        scans = await self.list_scans()
        for scan in scans:
            if scan["id"] == execution_id:
                return scan
        raise FileNotFoundError(f"Scan {execution_id} not found.")
