import os
import re
from pathlib import Path

app_gradle = Path("android/app/build.gradle.kts")
gradle_properties = Path("android/gradle.properties")

text = app_gradle.read_text()

ndk_dir = Path(os.environ["ANDROID_NDK"])
ndk_version = ndk_dir.name

# Flutter's generated project uses ndkVersion = flutter.ndkVersion.
# Replace every existing assignment so the CI-selected NDK is authoritative.
text, ndk_count = re.subn(
    r"(?m)^\s*ndkVersion\s*=\s*[^\n]+$",
    f'ndkVersion = "{ndk_version}"',
    text,
)
if ndk_count == 0:
    text = text.replace(
        "android {",
        f'''android {{
    ndkVersion = "{ndk_version}"
''',
        1,
    )

# Configure CMake for the PocketAI native library.
if "externalNativeBuild {" not in text:
    text = text.replace(
        "android {",
        '''android {
    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
        }
    }
''',
        1,
    )

# Flutter's target-platform flag does not always constrain externalNativeBuild.
# Explicitly restrict the Android native build to arm64-v8a.
text = re.sub(
    r"(?s)\n\s*ndk\s*\{\s*abiFilters\s*=\s*[^}]+\}",
    "",
    text,
)

default_config = re.search(r"(?m)^\s*defaultConfig\s*\{", text)
if not default_config:
    raise SystemExit("defaultConfig block was not found in android/app/build.gradle.kts")

insert_at = default_config.end()
text = (
    text[:insert_at]
    + '''
        ndk {
            abiFilters.clear()
            abiFilters += listOf("arm64-v8a")
        }
'''
    + text[insert_at:]
)

# The CI APK is an installable test artifact. The generated Flutter scaffold
# may leave release unsigned, so explicitly use the generated debug keystore
# for this non-production CI build. Production signing will be added separately.
release = re.search(r"(?s)buildTypes\s*\{.*?^\s*release\s*\{", text, re.MULTILINE)
if not release:
    raise SystemExit("release buildType block was not found in android/app/build.gradle.kts")

release_body_start = release.end()
next_block = text.find("\n    }", release_body_start)
if next_block == -1:
    raise SystemExit("release buildType closing block was not found")

release_body = text[release_body_start:next_block]
if "signingConfig" not in release_body:
    text = (
        text[:release_body_start]
        + '''
        signingConfig = signingConfigs.getByName("debug")
'''
        + text[release_body_start:]
    )

app_gradle.write_text(text)

# AGP understands this injected ABI property and uses it for native builds.
properties = gradle_properties.read_text() if gradle_properties.exists() else ""
properties = re.sub(
    r"(?m)^\s*android\.injected\.build\.abi\s*=.*$",
    "",
    properties,
)
if properties and not properties.endswith("\n"):
    properties += "\n"
properties += "android.injected.build.abi=arm64-v8a\n"
gradle_properties.write_text(properties)

print("Configured Android native build:")
print(f"  ndkVersion = {ndk_version}")
print("  abiFilters = arm64-v8a")
print("  android.injected.build.abi = arm64-v8a")
print("  release signing = debug keystore (CI test artifact)")
