import os
import re
from pathlib import Path

path = Path("android/app/build.gradle.kts")
text = path.read_text()

ndk_dir = Path(os.environ["ANDROID_NDK"])
ndk_version = ndk_dir.name

# Flutter's generated project may use either:
#   ndkVersion = flutter.ndkVersion
# or a quoted version. Replace either form with the CI-selected NDK.
if re.search(r"ndkVersion\s*=\s*[^\n]+", text):
    text = re.sub(
        r"ndkVersion\s*=\s*[^\n]+",
        f'ndkVersion = "{ndk_version}"',
        text,
        count=1,
    )
else:
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

# Restrict the native build to the supported Android ABI.
abi_block = '''ndk {
            abiFilters += listOf("arm64-v8a")
        }'''
if "abiFilters" not in text:
    text = text.replace(
        "defaultConfig {",
        f'''defaultConfig {{
        {abi_block}
''',
        1,
    )
else:
    text = re.sub(
        r"ndk\s*\{[^}]*abiFilters[^}]*\}",
        abi_block,
        text,
        count=1,
        flags=re.DOTALL,
    )

path.write_text(text)
