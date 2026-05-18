#!/bin/bash
set -e

# Required Env Vars: TARGET, GCS_BUCKET, EXECUTION_ID, UPLOAD_URL

if [ -z "$TARGET" ]; then
  echo "Error: TARGET env var is not set."
  exit 1
fi

if [ -z "$GCS_BUCKET" ]; then
  echo "Error: GCS_BUCKET env var is not set."
  exit 1
fi

if [ -z "$UPLOAD_URL" ]; then
  echo "Error: UPLOAD_URL env var is not set. Required for Signed URL upload."
  exit 1
fi

# Fallback for ID
EXECUTION_ID=${EXECUTION_ID:-$(date +%s)}
OUTPUT_FILE="/tmp/${EXECUTION_ID}.json"

# Detect target type dynamically
if [[ "$TARGET" =~ ^https?:// ]]; then
  TARGET_FLAG="--uri-target=$TARGET"
elif [[ "$TARGET" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  TARGET_FLAG="--ip-v4-target=$TARGET"
elif [[ "$TARGET" == *:* ]]; then
  TARGET_FLAG="--ip-v6-target=$TARGET"
else
  TARGET_FLAG="--hostname-target=$TARGET"
fi

echo "Starting Tsunami scan using flag: $TARGET_FLAG"
echo "Execution ID: $EXECUTION_ID"

# 1. Run Tsunami Scanner with JVM Container Memory Tuning
java -XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0 -XX:+UseG1GC \
  -cp "/usr/tsunami/tsunami.jar:/usr/tsunami/py_server" \
  -Dtsunami.config.location=/usr/tsunami/tsunami.yaml \
  com.google.tsunami.main.cli.TsunamiCli \
  "$TARGET_FLAG" \
  --scan-results-local-output-format=JSON \
  --scan-results-local-output-filename="$OUTPUT_FILE"

echo "Scan finished."

# 2. Upload to GCS using curl Signed URL
echo "Uploading results using Signed URL..."
curl -X PUT -H "Content-Type: application/json" -T "$OUTPUT_FILE" "$UPLOAD_URL"

# 3. Publish Completion Message to Pub/Sub
if [ -n "$PUBSUB_TOPIC" ]; then
  echo "Publishing completion event to Pub/Sub topic: $PUBSUB_TOPIC..."
  TOKEN=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token" -H "Metadata-Flavor: Google" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4 || true)
  
  if [ -n "$TOKEN" ]; then
    PAYLOAD=$(printf '{"messages":[{"data":"%s"}]}' "$(printf '{"execution_id":"%s"}' "$EXECUTION_ID" | base64 | tr -d '\n')")
    curl -s -X POST "https://pubsub.googleapis.com/v1/$PUBSUB_TOPIC:publish" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d "$PAYLOAD" || true
  fi
fi

echo ""
echo "Job completed successfully."


