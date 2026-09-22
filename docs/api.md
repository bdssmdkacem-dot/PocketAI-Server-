# PocketAI API v0.1

GET /health
GET /v1/models
POST /v1/chat/completions

The chat endpoint follows the OpenAI-compatible request shape:
model, messages, temperature, max_tokens, stream.

Streaming uses Server-Sent Events and terminates with data: [DONE].
