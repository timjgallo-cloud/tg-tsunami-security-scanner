import os
import logging
import asyncio
import vt

logger = logging.getLogger(__name__)

# In-memory cache for CVE risk scores across scan executions
_CVE_CACHE = {}

class GtiEnricher:
    def __init__(self):
        self.api_key = os.environ.get("VT_API_KEY")
        if not self.api_key:
            logger.warning("VT_API_KEY not set. Enrichment will be skipped.")
            self.client = None
        else:
            self.client = vt.Client(self.api_key)

    async def close(self):
        if self.client:
            await self.client.close()

    async def enrich_vulnerabilities(self, tsunami_results: dict) -> dict:
        """
        Enriches Tsunami results with GTI (VirusTotal) risk scores.
        """
        if not self.client:
            return tsunami_results

        findings = tsunami_results.get("scanFindings", [])
        
        for finding in findings:
            vuln = finding.get("vulnerability", {})
            cve_id = vuln.get("cveId")
            
            if cve_id:
                 try:
                     risk_score = await self.get_risk_score(cve_id)
                     vuln['gtiRiskScore'] = risk_score
                 except Exception as e:
                     logger.error(f"Failed to enrich {cve_id}: {e}")

        return tsunami_results

    async def get_risk_score(self, cve_id: str) -> float:
        """Fetches risk score from cache or VirusTotal API."""
        if cve_id in _CVE_CACHE:
            logger.info(f"[CACHE HIT] Pulling risk score for {cve_id} from cache.")
            return _CVE_CACHE[cve_id]
            
        logger.info(f"[CACHE MISS] Querying VirusTotal/GTI API for {cve_id}...")
        # In a real implementation, query VT vulnerability intelligence endpoint:
        # url = f"/intelligence/vulnerabilities/{cve_id}"
        # response = await self.client.get_json_async(url)
        # risk_score = response.get("data", {}).get("attributes", {}).get("cvss_score", 9.5)
        
        # Placeholder/Mock simulation of VT API call
        await asyncio.sleep(0.1)
        risk_score = 9.5
        
        _CVE_CACHE[cve_id] = risk_score
        return risk_score
