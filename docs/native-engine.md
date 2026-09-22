# Native engine build

PocketAI uses the upstream llama.cpp source as a pinned CI dependency.

Current pin:
- Repository: https://github.com/ggml-org/llama.cpp
- Commit: f95b0d95394d5e311ba8228689972843178c5e28
- Target: Android arm64-v8a
- Android API: 28
- GGML native CPU detection: disabled for cross-compilation
- OpenMP, OpenSSL, llamafile and standalone tools/examples are disabled for the Android library smoke build

The source is fetched during GitHub Actions instead of being vendored into this repository. This keeps the application repository small while making the native dependency reproducible.

This stage only proves that the upstream inference library can be configured and compiled for the Android target. It does not yet connect the library to the Flutter UI or load a GGUF model.
