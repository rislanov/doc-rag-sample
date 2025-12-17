#!/bin/bash
# Test script for DocRAG API

set -e

API_URL="${API_URL:-http://localhost:8080}"

echo "Testing DocRAG API at $API_URL"
echo "================================"

# Health check
echo -e "\n1. Health Check..."
curl -s "$API_URL/api/health" | jq .

# Test search (will return empty if no data)
echo -e "\n2. Testing Search..."
curl -s -X POST "$API_URL/api/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "договор",
    "limit": 5
  }' | jq .

# Test query (will use LLM)
echo -e "\n3. Testing RAG Query..."
curl -s -X POST "$API_URL/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Расскажи о документах",
    "maxChunks": 3
  }' | jq .

echo -e "\n================================"
echo "Tests completed!"
