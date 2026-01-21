#!/usr/bin/env bash

SERVER_HOST="http://127.0.0.1:8000"
AUTH_TOKEN="${SQUIRREL_GATEWAY_API_KEY:-lgw-5196e201d436d62b7e883755a65fa70b}"

curl $SERVER_HOST/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"hello？"}],"stream":true}'

curl $SERVER_HOST/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{"model":"claude-haiku-4-5","messages":[{"role":"user","content":"hello？"}],"stream":true}'


curl $SERVER_HOST/v1/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"hello？"}],"stream":true}'

curl $SERVER_HOST/v1/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{"model":"claude-haiku-4-5","messages":[{"role":"user","content":"hello？"}],"stream":true}'

curl $SERVER_HOST/v1/embeddings \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "The food was delicious and the waiter...",
    "model": "text-embedding-3-small",
    "encoding_format": "float"
   }'