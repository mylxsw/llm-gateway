#!/usr/bin/env bash

SERVER_HOST="http://127.0.0.1:8000"
AUTH_TOKEN="lgw-a83aeb7131fbcc02aa9a20685c3d9c9b"

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

