# GCP Argolis Deployment, Verification & Testing Guide

This guide provides comprehensive, step-by-step instructions for deploying, verifying, and testing the Tsunami Security Scanner with the "Stitch" Web UI inside a **GCP Argolis** demonstration environment.

---

## 📌 Introduction to Argolis Constraints

Google **Argolis** is a powerful environment for customer-facing proof-of-concept (PoC) demonstrations. However, because it is managed within the corporate Google Cloud organization, several security policies and constraints are enforced by default.

### ⚠️ Critical Organization Policies to Watch

1. **Domain Restricted Ingress (`constraints/iam.allowedPolicyMemberDomains`)**:
   * **Impact**: Standard Terraform configurations allow public ingress (`allUsers`) on the Web UI Cloud Run service so external testers can reach it. In Argolis, this is blocked. Attempting to apply the unmodified Terraform configuration will result in an IAM permission error.
   - **Workaround**: Grant invoker permissions strictly to `domain:google.com` or specific `@google.com` user identities instead of `allUsers`.
2. **Disable Service Account Key Creation (`constraints/iam.disableServiceAccountKeyCreation`)**:
   * **Impact**: Generating local JSON private keys for service accounts is blocked by policy.
   - **Workaround**: Never generate or download SA JSON keys. Rely on Application Default Credentials (ADC) through the `gcloud` CLI and use Cloud Run's native runtime service identities.

---

## 🔑 Prerequisites & Authentication

Ensure your local terminal is authenticated using your **corporate `@google.com` credentials**:

```bash
# 1. Authenticate your gcloud CLI
gcloud auth login

# 2. Authenticate Application Default Credentials (ADC) for Terraform
gcloud auth application-default login

# 3. Configure your active Argolis project
gcloud config set project <YOUR_ARGOLIS_PROJECT_ID>
```

---

## 🛠️ Step-by-Step Argolis Deployment

### Step 1: Configure Ingress Restrictions in Terraform

Before launching Terraform, you must modify the public access rule in `terraform/main.tf` to conform to Argolis Domain Restricted Ingress rules.

Modify [terraform/main.tf](file:///Users/timjgallo/tjg-python/tsunami-repo-clone/tg-tsunami-security-scanner/terraform/main.tf#L170-L176) as follows:

```diff
-# Allow public access to Web UI (for demo purposes - secure this in production!)
-resource "google_cloud_run_service_iam_member" "public_access" {
-  service  = google_cloud_run_service.web_ui_service.name
-  location = google_cloud_run_service.web_ui_service.location
-  role     = "roles/run.invoker"
-  member   = "allUsers"
-}
+# Restrict access strictly to the Google Domain (Argolis Compliance)
+resource "google_cloud_run_service_iam_member" "public_access" {
+  service  = google_cloud_run_service.web_ui_service.name
+  location = google_cloud_run_service.web_ui_service.location
+  role     = "roles/run.invoker"
+  member   = "domain:google.com"
+}
```

> [!IMPORTANT]
> Applying this change restricts the UI endpoints to users signed in with a `@google.com` or `@demoland.com` workspace account.

---

### Step 2: Launch Interactive Infrastructure Setup

Run the configuration script. It will prompt for your Argolis project details and securely provision GCS buckets, service accounts, Artifact Registry repositories, and Cloud Run skeletons:

```bash
chmod +x setup.sh
./setup.sh
```

**Prompts & Values:**
* **Google Cloud Project ID**: `<YOUR_ARGOLIS_PROJECT_ID>`
* **Target Region**: `us-central1`
* **GTI / VirusTotal API Key**: Input your Personal VirusTotal Key (obtain from [VirusTotal API Settings](https://www.virustotal.com/gui/user/apikey) to enable dynamic risk scoring).

---

### Step 3: Build & Push Docker Containers

You can build and push the containers either **locally using Docker** or **remotely using Google Cloud Build** (highly recommended in Cloud Shell environments as it requires no local Docker setup).

#### Option A: Build Remotely with Google Cloud Build (Recommended)
Run these commands from the repository root to build and push directly to your Artifact Registry remotely:

```bash
# 1. Build the Scanner Job remotely
gcloud builds submit --config cloudbuild.scanner.yaml .

# 2. Build the Web UI Service remotely
gcloud builds submit --tag us-central1-docker.pkg.dev/<YOUR_ARGOLIS_PROJECT_ID>/tsunami-repo/tsunami-web-ui:latest ./web_ui
```

#### Option B: Build and Push Locally using Docker
If you have a local Docker daemon running and configured:

```bash
# 1. Authenticate Docker to Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# 2. Build and Push the Scanner Job
docker build -t us-central1-docker.pkg.dev/<YOUR_ARGOLIS_PROJECT_ID>/tsunami-repo/tsunami-scanner:latest -f cloud.Dockerfile .
docker push us-central1-docker.pkg.dev/<YOUR_ARGOLIS_PROJECT_ID>/tsunami-repo/tsunami-scanner:latest

# 3. Build and Push the Web UI Service
cd web_ui
docker build -t us-central1-docker.pkg.dev/<YOUR_ARGOLIS_PROJECT_ID>/tsunami-repo/tsunami-web-ui:latest .
docker push us-central1-docker.pkg.dev/<YOUR_ARGOLIS_PROJECT_ID>/tsunami-repo/tsunami-web-ui:latest
cd ..
```

---

## 🧪 Testing Scenarios in Argolis

### Scenario 1: Local High-Fidelity Verification (Mock Mode)

Use this scenario to test the FastAPI rendering, signed GCS uploads, and threat intelligence logic locally without incurring GAE or Cloud Run execution charges:

```bash
cd web_ui
# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure local mock variables
export LOCAL_MODE="true"
export PROJECT_ID="argolis-mock"
export SCANNER_JOB_NAME="mock-scanner"
export GCS_BUCKET="mock-bucket"
export VT_API_KEY="mock-key"

# Start FastAPI local server
uvicorn main:app --host 127.0.0.1 --port 8080 --reload
```
* **Action**: Open `http://127.0.0.1:8080` in your browser and input `127.0.0.1`. 
* **Result**: You can initiate a mock scan, monitor the simulated upload, and inspect the threat-enriched results immediately.

---

### Scenario 2: Deployed External Domain Scan

Validate that the live serverless scanner successfully resolves external targets and uploads reports to your GCS findings bucket:

1. Open the Cloud Run URL printed in the Terraform execution output.
2. Input `scanme.nmap.org` in the Target hostname field.
3. Click **Trigger Security Scan**.
4. Keep an eye on the Cloud Run Jobs Console or verify the execution status in your terminal:
   ```bash
   gcloud beta run jobs executions list --job=tsunami-scanner --region=us-central1 --limit=5
   ```
5. Confirm that the raw results JSON `{execution_id}.json` and the enriched threat report `{execution_id}_enriched.json` are generated in your project storage bucket:
   ```bash
   gcloud storage ls gs://<YOUR_ARGOLIS_PROJECT_ID>-tsunami-results/
   ```

---

### Scenario 3: VPC Internal Scanning (High-Fidelity Lab)

To demonstrate Tsunami's core vulnerability detection capability against internal infrastructure inside the same Argolis environment:

#### 1. Deploy a Vulnerable Target VM
Spin up a simple Debian GCE Instance in the `default` VPC network:
```bash
gcloud compute instances create vulnerable-target-vm \
    --zone=us-central1-a \
    --image-family=debian-12 \
    --image-project=debian-cloud \
    --machine-type=e2-micro \
    --metadata=startup-script="apt-get update && apt-get install -y apache2"
```

#### 2. Access Target and Install a Test Vulnerability
SSH into the VM and install an older, vulnerable application, or configure a mock open-port service. For quick verification, configure Apache to expose a sample directory listing.

#### 3. Configure VPC Firewall Rules
Allow internal traffic from the Cloud Run IP range (or simply allow the VPC subnet range for testing):
```bash
gcloud compute firewall-rules create allow-internal-tsunami \
    --network=default \
    --allow=tcp:80,tcp:22 \
    --source-ranges=10.0.0.0/8,35.191.0.0/16,130.211.0.0/22
```

#### 4. Launch Internal Scan
Find the internal IP of your target VM:
```bash
gcloud compute instances describe vulnerable-target-vm --zone=us-central1-a --format="value(networkInterfaces[0].networkIP)"
```
Input this internal IP (e.g., `10.128.0.2`) in your Tsunami Web UI dashboard, click **Trigger Security Scan**, and monitor target assessment results in the dashboard findings panel.

---

## 🧹 Resource Cleanup

Argolis resources should be cleanly torn down when a PoC is finished to prevent resource limits from capping your demo capabilities:

```bash
# Destroy all deployed infrastructure in GCP
cd terraform
terraform destroy -auto-approve

# Delete target GCE instance
gcloud compute instances delete vulnerable-target-vm --zone=us-central1-a --quiet
```
