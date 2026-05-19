
# Stage 1: Build the Tsunami JAR (reusing logic from core.Dockerfile)
FROM ghcr.io/google/tsunami-scanner-devel:latest AS build

WORKDIR /usr/repos/tsunami-security-scanner
# Copy only source and build configuration files to leverage Docker layer caching
COPY gradlew settings.gradle settings.gradle build.gradle init.gradle ./
COPY gradle/ ./gradle/
COPY proto/ ./proto/
COPY common/ ./common/
COPY plugin/ ./plugin/
COPY plugin_server/ ./plugin_server/
COPY workflow/ ./workflow/
COPY main/ ./main/
COPY tsunami.yaml ./
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

# Pull standard Tsunami plugins
FROM ghcr.io/google/tsunami-plugins-google:latest AS plugins-google
FROM ghcr.io/google/tsunami-plugins-templated:latest AS plugins-templated
FROM ghcr.io/google/tsunami-plugins-doyensec:latest AS plugins-doyensec
FROM ghcr.io/google/tsunami-plugins-community:latest AS plugins-community
FROM ghcr.io/google/tsunami-plugins-govtech:latest AS plugins-govtech
FROM ghcr.io/google/tsunami-plugins-facebook:latest AS plugins-facebook

# Stage 2: Final Cloud Image
FROM eclipse-temurin:21-jre-jammy

# Install system deps
RUN apt-get update && apt-get install -y \
    curl \
    nmap \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/tsunami

# Copy Tsunami artifacts from build
COPY --from=build /usr/tsunami/tsunami.jar .
COPY --from=build /usr/tsunami/tsunami.yaml .
COPY --from=build /usr/tsunami/payload_definitions.yaml .
COPY --from=build /usr/tsunami/py_server/ ./py_server/

# Copy standard Tsunami plugins
COPY --from=plugins-google /usr/tsunami/plugins/ /usr/tsunami/plugins/
COPY --from=plugins-templated /usr/tsunami/plugins/ /usr/tsunami/plugins/
COPY --from=plugins-doyensec /usr/tsunami/plugins/ /usr/tsunami/plugins/
COPY --from=plugins-community /usr/tsunami/plugins/ /usr/tsunami/plugins/
COPY --from=plugins-govtech /usr/tsunami/plugins/ /usr/tsunami/plugins/
COPY --from=plugins-facebook /usr/tsunami/plugins/ /usr/tsunami/plugins/

# Copy entrypoint
COPY cloud_entrypoint.sh /usr/tsunami/cloud_entrypoint.sh
RUN chmod +x /usr/tsunami/cloud_entrypoint.sh

# Environment variables
ENV TARGET=""
ENV GCS_BUCKET=""

ENTRYPOINT ["/usr/tsunami/cloud_entrypoint.sh"]
