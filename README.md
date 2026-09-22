# PocketAI Server

**PocketAI Server** turns an Android phone into a self-contained local AI server powered by **llama.cpp** and **GGUF** models.

The project is being developed toward a **complete, publishable Android application**, not a temporary MVP. The development strategy is deliberately phone-first: build and validate the application through GitHub Actions, install APKs on a real Android phone, verify every major capability on-device, and only create the production release keystore and signed release bundle after the product is functionally complete.

> **Current status:** active development. The native build pipeline works, but APK installation on the target phone is still being diagnosed. No production signing is being created yet.

Repository: https://github.com/bdssmdkacem-dot/PocketAI-Server-

---

## Product vision

PocketAI Server will make an Android phone usable as a **local AI inference server** on the user's LAN.

The final application is intended to provide:

- local GGUF model execution through llama.cpp
- ARM64 Android native inference
- OpenAI-compatible HTTP API
- streaming chat completions
- local/LAN server operation
- API-key authentication
- model download, selection, loading and unloading
- foreground-service operation while the UI is closed
- server status and performance monitoring
- request and inference logs
- an in-app API playground
- device and engine diagnostics
- robust error handling and recovery
- production-ready Android packaging

The phone remains the place where the model runs. No cloud AI provider is required for inference.

---

## Target architecture

```text
┌──────────────────────────────────────────────┐
│                 PocketAI App                 │
├──────────────────────────────────────────────┤
│ Flutter UI                                   │
│                                              │
│ Dashboard • Models • Server • API • Logs     │
│ Diagnostics • Settings                      │
├──────────────────────────────────────────────┤
│ Android Native Layer                         │
│                                              │
│ Foreground Service                           │
│ HTTP Server                                  │
│ Notifications                                │
│ Network / lifecycle management               │
├──────────────────────────────────────────────┤
│ JNI / Native Bridge                          │
│                                              │
│ libpocket_ai.so                              │
│ llama.cpp                                    │
│ GGML                                         │
├──────────────────────────────────────────────┤
│ Local model storage                          │
│                                              │
│ GGUF models                                  │
└──────────────────────────────────────────────┘
```

### Runtime flow

```text
Flutter UI
    │
    ▼
Android service/controller
    │
    ▼
HTTP API
    │
    ▼
Native JNI bridge
    │
    ▼
llama.cpp
    │
    ▼
GGUF model
    │
    ▼
Generated tokens
    │
    ▼
HTTP streaming response
```

---

## OpenAI-compatible API

The server is designed around an OpenAI-compatible API so existing clients can communicate with the Android phone without a PocketAI-specific protocol.

Planned endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /health` | Server health |
| `GET /v1/status` | Runtime/server status |
| `GET /v1/models` | Installed/available models |
| `POST /v1/chat/completions` | Chat generation |
| `POST /v1/completions` | Completion generation |

Streaming will use an HTTP streaming/SSE-compatible response for token-by-token generation.

Example request:

```http
POST /v1/chat/completions
Authorization: Bearer pk_xxxxxxxxx
Content-Type: application/json
```

```json
{
  "model": "qwen2.5-1.5b-instruct",
  "messages": [
    {
      "role": "user",
      "content": "Hello from PocketAI"
    }
  ],
  "stream": true
}
```

---

## Android server mode

The production application will not depend on keeping the Flutter screen open.

The intended lifecycle is:

```text
Open PocketAI
      ↓
Select/load model
      ↓
Start server
      ↓
Foreground service
      ↓
Android notification shows server status
      ↓
User may close the UI
      ↓
Server continues according to Android system rules
```

The foreground service implementation will follow the Android platform requirements for foreground-service declarations, permissions, service types and background-start restrictions.

Android documentation:

- https://developer.android.com/develop/background-work/services/fgs
- https://developer.android.com/develop/background-work/services/fgs/declare
- https://developer.android.com/develop/background-work/services/fgs/launch

---

## Model management

Models will not be bundled into the APK.

The application will maintain a local model directory and manage model lifecycle:

```text
Model catalog
    │
    ├── Download
    ├── Verify
    ├── Store
    ├── Select
    ├── Load
    ├── Unload
    └── Delete
```

Planned model metadata:

- name
- architecture
- quantization
- file size
- SHA-256
- context length
- estimated memory requirement
- installation state
- active/inactive state

The application will also inspect device capabilities such as:

- Android version
- ARM ABI
- CPU information
- available RAM
- available storage

This information will be used to make technically appropriate model recommendations.

---

## Security

LAN access must not mean unauthenticated access.

The production server will support an API key:

```http
Authorization: Bearer pk_xxxxxxxxx
```

Planned controls:

- API key generation
- API key regeneration
- localhost-only mode
- LAN mode
- configurable server port
- clear authentication errors
- safe default configuration

The application will not expose a production API without an explicit server configuration.

---

## In-app API Playground

The application will include a local testing interface so the complete API can be tested directly from the Android phone.

Example:

```text
┌─────────────────────────────────────┐
│ API Playground                      │
│                                     │
│ Model: Qwen 2.5 1.5B Q4_K_M        │
│                                     │
│ Explain quantum computing           │
│                                     │
│             [ SEND ]                 │
│                                     │
│ 9.4 tok/s                           │
│ 143 ms latency                      │
│ 128 tokens                          │
└─────────────────────────────────────┘
```

This reduces dependence on a PC during development and makes the phone itself a complete test client.

---

## Diagnostics

A dedicated diagnostics screen will verify the complete local stack.

Planned checks:

```text
Android environment       ✓
ARM64 support             ✓
RAM / storage             ✓
Native library            ✓
llama.cpp                 ✓
Model file                ✓
Model loading             ✓
JNI bridge                ✓
HTTP server               ✓
OpenAI API                ✓
Streaming                 ✓
Authentication            ✓
Foreground service        ✓
Network accessibility     ✓
Request generation        ✓
```

The goal is to make failures observable from the phone rather than requiring ADB access.

---

## Reliability testing

Before production release, the application will be tested on the real Android phone for:

- first installation
- upgrade installation
- application launch
- native library loading
- model loading
- model unloading
- repeated inference
- streaming responses
- invalid API requests
- invalid API keys
- server start/stop
- server restart
- closing the Flutter UI
- locking the phone
- screen-off behavior
- Wi-Fi disconnect/reconnect
- network address changes
- low available storage
- low-memory conditions
- repeated requests
- large context requests
- malformed model files
- corrupted/incomplete downloads
- recovery after native/server errors

A feature is not considered complete merely because it compiles.

---

## Phone-first development strategy

The development environment is intentionally optimized for a workflow without local ADB access.

```text
GitHub repository
       │
       ▼
GitHub Actions
       │
       ├── Analyze
       ├── Test
       ├── Native build
       ├── APK validation
       └── APK artifact
                │
                ▼
         Android phone
                │
                ├── Install
                ├── Run
                ├── Test
                └── Validate
```

GitHub Actions also provides automated Android-emulator diagnostics where practical.

The diagnostic workflow can validate APK metadata, signatures, native libraries and PackageManager installation behavior. Manual workflow execution is supported through GitHub Actions `workflow_dispatch`.

GitHub Actions documentation:

https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows

---

## Development phases

### Phase 0 — Build and installation foundation

- Flutter Android project
- Android native integration
- llama.cpp integration
- ARM64 packaging
- APK signing for test builds
- APK static diagnostics
- PackageManager installation diagnostics

**Current priority:** finish this phase and determine why the current APK is rejected by the target phone.

---

### Phase 1 — Native inference

- JNI bridge
- native library loading
- llama.cpp initialization
- GGUF model loading
- inference
- unload/reload
- native error reporting

**Exit condition:** a real GGUF model generates text reliably on the target phone.

---

### Phase 2 — Local HTTP server

- HTTP listener
- configurable port
- health endpoint
- status endpoint
- models endpoint
- request validation
- structured error responses

**Exit condition:** another device on the same LAN can communicate with the phone.

---

### Phase 3 — OpenAI-compatible API

- `/v1/models`
- `/v1/chat/completions`
- `/v1/completions`
- streaming
- usage/token statistics
- authentication

**Exit condition:** an external OpenAI-compatible client can use the phone as its local endpoint.

---

### Phase 4 — Android service

- foreground service
- persistent server state
- notification
- start/stop controls
- lifecycle handling
- Android-version compatibility
- battery/power behavior testing

**Exit condition:** the server remains usable when the Flutter UI is no longer visible, within Android's platform restrictions.

---

### Phase 5 — Model management

- model catalog
- download
- resume/retry
- integrity verification
- storage management
- model selection
- model unloading
- model metadata

**Exit condition:** models can be managed entirely from the phone.

---

### Phase 6 — Complete UI

Planned sections:

```text
Dashboard
Models
Server
API Playground
Logs
Diagnostics
Settings
```

Dashboard metrics will include, where available:

- server state
- selected model
- generation speed
- latency
- request count
- token statistics
- memory information
- network address
- port

---

### Phase 7 — Reliability and security

- authentication hardening
- malformed-request handling
- model corruption handling
- network failure recovery
- memory pressure handling
- lifecycle testing
- server recovery
- safe defaults
- production logging policy

---

### Phase 8 — Production release

Only after the application passes the phone-based functional test cycle:

1. Freeze production functionality.
2. Create the production release/upload keystore.
3. Store signing material only in GitHub Secrets.
4. Build signed release APK/AAB.
5. Verify package metadata.
6. Verify signing.
7. Verify native ABIs.
8. Install and test the signed release on the phone.
9. Create the production release in Google Play Console.
10. Perform final Play Console checks.
11. Publish.

**Production signing is intentionally postponed until this stage.**

---

## CI/CD

Planned workflow separation:

```text
.github/workflows/

android-ci.yml
    ├── analyze
    ├── test
    └── build

pocketai-diagnostic.yml
    ├── APK inspection
    ├── native inspection
    ├── signing verification
    └── Android PackageManager diagnostics

android-release.yml
    ├── release build
    ├── production signing
    ├── verification
    └── release artifact
```

The production workflow will not be used as a substitute for functional testing.

---

## Release signing policy

No production keystore is required during the development/testing phase.

Test builds may use a dedicated debug/test signing key.

The final production credentials will be kept outside the repository using GitHub encrypted secrets.

Never commit:

- `.jks`
- `.keystore`
- signing passwords
- private keys
- release credentials

---

## Repository structure

The project is expected to evolve toward:

```text
PocketAI-Server-/
├── lib/
│   ├── main.dart
│   ├── core/
│   ├── features/
│   │   ├── dashboard/
│   │   ├── models/
│   │   ├── server/
│   │   ├── playground/
│   │   ├── logs/
│   │   └── diagnostics/
│   └── services/
│
├── android/
│   ├── app/
│   │   └── src/main/
│   │       ├── kotlin/
│   │       ├── cpp/
│   │       └── AndroidManifest.xml
│   └── pocketai_template/
│
├── scripts/
│   ├── fetch_llama_cpp.sh
│   └── configure_android_native.py
│
├── .github/
│   └── workflows/
│       ├── android-ci.yml
│       ├── pocketai-diagnostic.yml
│       └── android-release.yml
│
├── test/
├── README.md
└── pubspec.yaml
```

The exact structure may evolve as implementation grows; functionality and testability take priority over prematurely freezing directories.

---

## Definition of done

PocketAI Server will be considered ready for production only when all of the following are true:

- [ ] APK installs successfully on the target phone
- [ ] Application launches normally
- [ ] Native libraries load correctly
- [ ] llama.cpp initializes correctly
- [ ] GGUF model loads correctly
- [ ] Inference works on the target phone
- [ ] Streaming works
- [ ] HTTP server works
- [ ] OpenAI-compatible endpoints work
- [ ] API authentication works
- [ ] LAN access works as configured
- [ ] Foreground service works
- [ ] Server survives the intended lifecycle tests
- [ ] Model management works
- [ ] Logs are usable
- [ ] Diagnostics pass
- [ ] Flutter tests pass
- [ ] Static APK validation passes
- [ ] Release APK/AAB installs and runs on the target phone
- [ ] Production signing is verified
- [ ] No development-only credentials are included
- [ ] Play Store release requirements are checked

**Until these conditions are satisfied, the project remains in development/testing and is not treated as a production release.**

---

## Current blocker

The current APK build succeeds, but the target Android phone reports:

```text
L'application n'a pas été installée,
car le package semble ne pas être valide.
```

The project therefore prioritizes identifying the exact Android PackageManager installation failure before making further architectural changes.

The dedicated diagnostic workflow is:

```
.github/workflows/pocketai-diagnostic.yml
```

The diagnostic uses a GitHub-hosted Android emulator to obtain a concrete `INSTALL_FAILED_*` or related PackageManager result where possible.

---

## Guiding principles

1. **Build the complete product, not a throwaway MVP.**
2. **Test the real APK on the real Android phone.**
3. **Use GitHub Actions for repeatable builds and diagnostics.**
4. **Do not guess when Android provides an exact installation/runtime error.**
5. **Keep native llama.cpp integration isolated and testable.**
6. **Do not create production signing credentials prematurely.**
7. **Do not publish until the complete functional test cycle passes.**
8. **Prefer local inference and local data by default.**
9. **Keep the API compatible with existing OpenAI-style clients.**
10. **Make failures diagnosable from the phone whenever possible.**

---

## License

License: **TBD**

The licenses of third-party components, including llama.cpp and model files, must be respected independently. Model redistribution rights depend on the individual model and its license.
