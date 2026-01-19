
# Stage 1: Build the Tsunami JAR (reusing logic from core.Dockerfile)
FROM ghcr.io/google/tsunami-scanner-devel:latest AS build

WORKDIR /usr/repos/tsunami-security-scanner
COPY . .
RUN mkdir -p /usr/tsunami
# Build fat jar
RUN gradle shadowJar

# Copy artifacts
RUN find . -name 'tsunami-main-*.jar' -exec cp {} /usr/tsunami/tsunami.jar \;
RUN cp ./tsunami.yaml /usr/tsunami/tsunami.yaml
RUN cp plugin/src/main/resources/com/google/tsunami/plugin/payload/payload_definitions.yaml /usr/tsunami/payload_definitions.yaml
# We copy py_server but plugins need to be built/installed if we use them
# For this basic example, we focus on the Core engine. 
# If Python plugins are needed, we need to generate protos as in core.Dockerfile
RUN cp -r plugin_server/py/ /usr/tsunami/py_server

# Patch payload path
RUN sed -i "s%'../../plugin/src/main/resources/com/google/tsunami/plugin/payload/payload_definitions.yaml'%'/usr/tsunami/payload_definitions.yaml'%g" \
      /usr/tsunami/py_server/plugin/payload/payload_utility.py

# Generate protos
WORKDIR /usr/repos/tsunami-security-scanner/
RUN python3 -m grpc_tools.protoc \
  -I/usr/repos/tsunami-security-scanner/proto \
  --python_out=/usr/tsunami/py_server/ \
  --grpc_python_out=/usr/tsunami/py_server/ \
  /usr/repos/tsunami-security-scanner/proto/*.proto

# Stage 2: Final Cloud Image
FROM python:3.11-slim

# Install Java and system deps
RUN apt-get update && apt-get install -y \
    openjdk-17-jre-headless \
    curl \
    nmap \
    && rm -rf /var/lib/apt/lists/*

# Install Google Cloud Storage lib for the upload script
RUN pip install google-cloud-storage

WORKDIR /usr/tsunami

# Copy Tsunami artifacts from build
COPY --from=build /usr/tsunami/tsunami.jar .
COPY --from=build /usr/tsunami/tsunami.yaml .
COPY --from=build /usr/tsunami/payload_definitions.yaml .
COPY --from=build /usr/tsunami/py_server/ ./py_server/

# Copy entrypoint
COPY cloud_entrypoint.sh /usr/tsunami/cloud_entrypoint.sh
RUN chmod +x /usr/tsunami/cloud_entrypoint.sh

# Environment variables
ENV TARGET=""
ENV GCS_BUCKET=""

ENTRYPOINT ["/usr/tsunami/cloud_entrypoint.sh"]
