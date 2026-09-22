# PocketAI Server Architecture

Flutter UI -> MethodChannel -> Kotlin Android -> JNI -> C++/llama.cpp -> GGUF model.

LAN clients connect to an HTTP server on the Android device.

Planned endpoints:
- GET /health
- GET /v1/models
- POST /v1/chat/completions

Models are downloaded separately from the APK. Production will use an Android foreground service and API-key protected LAN access.
