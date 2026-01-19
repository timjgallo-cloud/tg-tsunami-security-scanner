
#!/bin/bash
set -e

# Required Env Vars: TARGET, GCS_BUCKET, EXECUTION_ID

if [ -z "$TARGET" ]; then
  echo "Error: TARGET env var is not set."
  exit 1
fi

if [ -z "$GCS_BUCKET" ]; then
  echo "Error: GCS_BUCKET env var is not set."
  exit 1
fi

# Fallback for ID
EXECUTION_ID=${EXECUTION_ID:-$(date +%s)}
OUTPUT_FILE="/tmp/${EXECUTION_ID}.json"

echo "Starting Tsunami scan for target: $TARGET"
echo "Execution ID: $EXECUTION_ID"

# 1. Run Tsunami Scanner
# Adjust the classpath and flags as needed for the specific Tsunami build
# We assume the jar is at /usr/tsunami/tsunami.jar
java -cp "/usr/tsunami/tsunami.jar:/usr/tsunami/py_server" \
  -Dtsunami-config.location=/usr/tsunami/tsunami.yaml \
  com.google.tsunami.main.cli.TsunamiCli \
  --ip-v4-target="$TARGET" \
  --scan-results-local-output-format=JSON \
  --scan-results-local-output-filename="$OUTPUT_FILE" \
  --conf="/usr/tsunami/tsunami.yaml" \
  --scan-results-local-output-json-include-full-plugin-response=true # Optional: for more details

echo "Scan finished."

# 2. Upload to GCS using Python
echo "Uploading results to gs://${GCS_BUCKET}/${EXECUTION_ID}.json..."

python3 - <<EOF
from google.cloud import storage
import os

bucket_name = "${GCS_BUCKET}"
source_file_name = "${OUTPUT_FILE}"
destination_blob_name = "${EXECUTION_ID}.json"

try:
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)
    print(f"Successfully uploaded {source_file_name} to {destination_blob_name}")
except Exception as e:
    print(f"Failed to upload results: {e}")
    exit(1)
EOF

echo "Job completed successfully."
