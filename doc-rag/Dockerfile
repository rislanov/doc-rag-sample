FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# Copy csproj and restore
COPY DocRag.csproj .
RUN dotnet restore

# Copy everything else and build
COPY . .
RUN dotnet publish -c Release -o /app/publish

# Runtime image
FROM mcr.microsoft.com/dotnet/aspnet:8.0
WORKDIR /app

# Install curl for health checks and model verification
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY --from=build /app/publish .

# Set environment
ENV ASPNETCORE_URLS=http://+:8080
ENV ASPNETCORE_ENVIRONMENT=Production

EXPOSE 8080

# Startup script that waits for Ollama models
COPY <<EOF /app/entrypoint.sh
#!/bin/bash
set -e

echo "=== DocRAG API Service ==="

OLLAMA_URL=\${Ollama__BaseUrl:-http://ollama:11434}
LLM_MODEL=\${Ollama__Model:-mistral:7b-instruct}
EMBEDDING_MODEL=\${Ollama__EmbeddingModel:-evilfreelancer/enbeddrus}

echo "Waiting for Ollama at \$OLLAMA_URL..."

# Wait for Ollama API
max_wait=120
waited=0
until curl -sf "\$OLLAMA_URL/api/tags" > /dev/null 2>&1; do
    if [ \$waited -ge \$max_wait ]; then
        echo "WARNING: Ollama not available after \$max_wait seconds, starting anyway..."
        break
    fi
    echo "Ollama not ready, waiting... (\$waited/\$max_wait s)"
    sleep 5
    waited=\$((waited + 5))
done

echo "Verifying models are loaded..."
curl -sf "\$OLLAMA_URL/api/tags" | grep -q "mistral" && echo "LLM Model: OK" || echo "WARNING: LLM model may not be ready"
curl -sf "\$OLLAMA_URL/api/tags" | grep -q "enbeddrus" && echo "Embedding Model: OK" || echo "WARNING: Embedding model may not be ready"

echo ""
echo "Starting DocRAG API..."
exec dotnet DocRag.dll
EOF

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
