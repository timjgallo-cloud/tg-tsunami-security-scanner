# Tsunami

![build](https://github.com/google/tsunami-security-scanner/actions/workflows/core-build.yml/badge.svg)

Tsunami is a general purpose network security scanner with an extensible plugin
system for detecting high severity vulnerabilities with high confidence.

To learn more about Tsunami, visit our
[documentation](https://google.github.io/tsunami-security-scanner/).

Tsunami relies heavily on its plugin system to provide basic scanning
capabilities. All publicly available Tsunami plugins are hosted in a separate
[google/tsunami-security-scanner-plugins](https://github.com/google/tsunami-security-scanner-plugins)
repository.

## Quick start

Please see the documentation on how to
[build and run Tsunami](https://google.github.io/tsunami-security-scanner/howto/howto)

## Stitch Cloud UI Deployment

Deploy the Tsunami Security Scanner with the "Stitch" Web UI to Google Cloud Platform using Terraform and Cloud Run.

### Prerequisites
1. **Google Cloud Project**: You need a project ID (e.g., `my-security-project`).
2. **Tools Installed**: `terraform`, `gcloud`, and `docker`.
3. **Authentication**: Run `gcloud auth login` and `gcloud auth application-default login`.

### Step 1: Configuration & Infrastructure
We provide a setup script to configure your environment, including the **Google Threat Intelligence (GTI)** integration.

**Prerequisite:** Obtain a GTI (VirusTotal) API request key from [VirusTotal API Settings](https://www.virustotal.com/gui/user/apikey).

```bash
# Run the interactive setup script
./setup.sh
```
*This script will prompt for your Project ID, Region, and GTI API Key, then deploy the necessary infrastructure via Terraform.*

Alternatively, if you prefer manual Terraform execution:
```bash
cd terraform
terraform init
terraform apply -var="project_id=YOUR_ID" -var="vt_api_key=YOUR_KEY"
```

### Step 2: Build & Push Docker Images
Replace `YOUR_PROJECT_ID` with your actual project ID.

**1. Tsunami Scanner Engine**
```bash
# Return to root directory
cd ..
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT_ID/tsunami-repo/tsunami-scanner:latest -f cloud.Dockerfile .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT_ID/tsunami-repo/tsunami-scanner:latest
```

**2. Web UI**
```bash
cd web_ui
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT_ID/tsunami-repo/tsunami-web-ui:latest .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT_ID/tsunami-repo/tsunami-web-ui:latest
```

### Step 3: Access the UI
1. Go to the [Google Cloud Console - Cloud Run](https://console.cloud.google.com/run).
2. Find the `tsunami-web-ui` service.
3. Click the **URL** to open the dashboard.
4. Enter a target (e.g., `scanme.nmap.org`) to start a scan.

## Contributing

Read how to
[contribute to Tsunami](https://google.github.io/tsunami-security-scanner/contribute/).

## License

Tsunami is released under the [Apache 2.0 license](LICENSE).

```
Copyright 2025 Google Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

## Disclaimers

Tsunami is not an official Google product.
