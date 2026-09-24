import os
import re
from pathlib import Path

app_gradle = Path("android/app/build.gradle.kts")
gradle_properties = Path("android/gradle.properties")

text = app_gradle.read_text()

ndk_dir = Path(os.environ["ANDROID_NDK"])
abi = os.environ.get("POCKETAI_ABI", "arm64-v8a").strip()
if abi not in {"arm64-v8a", "x86_64"}:
    raise SystemExit(f"Unsupported POCKETAI_ABI: {abi}")
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
# Always configure the module-level CMake path explicitly. A generic
# "externalNativeBuild {" string search is unsafe because nested blocks
# may already exist in generated Flutter/AGP files.
if 'path = file("src/main/cpp/CMakeLists.txt")' not in text:
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
# Explicitly restrict the Android native build to the ABI selected by POCKETAI_ABI.
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
    + f'''\n        ndk {{\n            abiFilters.clear()\n            abiFilters += listOf("{abi}")\n        }}\n        externalNativeBuild {{\n            cmake {{\n                targets += listOf("pocket_ai")\n            }}\n        }}\n'''
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


# Explicitly register the JNI library directory so the prebuilt native runtime
# is unambiguously included in the Android main source set.
if 'jniLibs.srcDirs("src/main/jniLibs")' not in text:
    text = text.replace(
        "android {",
        '''android {
    sourceSets {
        getByName("main") {
            jniLibs.srcDirs("src/main/jniLibs")
        }
    }
''',
        1,
    )

# Keep JNI libraries uncompressed in the diagnostic APK.
if 'useLegacyPackaging = false' not in text:
    text = text.replace(
        "android {",
        '''android {
    packaging {
        jniLibs {
            useLegacyPackaging = false
        }
    }
''',
        1,
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
properties += f"android.injected.build.abi={abi}\n"
gradle_properties.write_text(properties)

print("Configured Android native build:")
print(f"  ndkVersion = {ndk_version}")
print(f"  abiFilters = {abi}")
print(f"  android.injected.build.abi = {abi}")
print("  release signing = debug keystore (CI test artifact)")
