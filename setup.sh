
#!/bin/bash
set -e

echo "=================================================="
echo "   Stitch Tsunami Scanner - Configuration Setup"
echo "=================================================="

# Prompt for Project ID
if [ -z "$PROJECT_ID" ]; then
    read -p "Enter your Google Cloud Project ID: " PROJECT_ID
fi

# Prompt for Region
if [ -z "$REGION" ]; then
    read -p "Enter Target Region [default: us-central1]: " REGION
    REGION=${REGION:-us-central1}
fi

# Prompt for VirusTotal/GTI API Key
if [ -z "$VT_API_KEY" ]; then
    echo ""
    echo "To enable Risk Scoring, you need a Google Threat Intelligence (VirusTotal) API Key."
    echo "Get one here: https://www.virustotal.com/gui/user/apikey"
    read -s -p "Enter your GTI/VirusTotal API Key: " VT_API_KEY
    echo ""
fi
# Prompt for Authorized Member (respect Argolis Domain Restricted Ingress)
if [ -z "$AUTHORIZED_MEMBER" ]; then
    ACTIVE_ACCOUNT=$(gcloud config get-value account 2>/dev/null || echo "")
    DEFAULT_MEMBER="domain:google.com"
    if [ -n "$ACTIVE_ACCOUNT" ]; then
        if [[ "$ACTIVE_ACCOUNT" == *"@google.com" ]]; then
            DEFAULT_MEMBER="domain:google.com"
        else
            DEFAULT_MEMBER="user:$ACTIVE_ACCOUNT"
        fi
    fi
    echo ""
    echo "Due to Argolis Domain Restricted Ingress policies, you must specify an authorized IAM member"
    echo "to access the Web UI (e.g., domain:google.com or user:your-email@domain.com)."
    read -p "Enter Authorized Member [default: $DEFAULT_MEMBER]: " AUTHORIZED_MEMBER
    AUTHORIZED_MEMBER=${AUTHORIZED_MEMBER:-$DEFAULT_MEMBER}
fi

echo ""
echo "--------------------------------------------------"
echo "Configuration Summary:"
echo "Project ID : $PROJECT_ID"
echo "Region     : $REGION"
echo "GTI Key    : ${VT_API_KEY:0:5}****************"
echo "IAM Member : $AUTHORIZED_MEMBER"
echo "--------------------------------------------------"
echo ""
read -p "Proceed with Terraform Deployment? (y/n): " CONFIRM

if [[ "$CONFIRM" != "y" ]]; then
    echo "Aborted."
    exit 0
fi

# Export for Terraform
export TF_VAR_project_id="$PROJECT_ID"
export TF_VAR_region="$REGION"
export TF_VAR_vt_api_key="$VT_API_KEY"
export TF_VAR_authorized_member="$AUTHORIZED_MEMBER"

echo "Initializing Terraform..."
cd terraform
terraform init

echo "Applying Terraform configuration..."
terraform apply -auto-approve

echo ""
echo "✅ Infrastructure Deployed Successfully."
echo ""
echo "Next Steps:"
echo "1. Build and Push the Docker images (see README.md)."
echo "2. Access your Web UI URL from the Terraform output."
