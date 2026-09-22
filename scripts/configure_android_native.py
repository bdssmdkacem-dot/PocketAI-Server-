import os
from pathlib import Path

path = Path("android/app/build.gradle.kts")
text = path.read_text()

ndk_dir = Path(os.environ["ANDROID_NDK"])
ndk_version = ndk_dir.name

if 'externalNativeBuild {' not in text:
    text = text.replace(
        'android {',
        f'''android {{
    ndkVersion = "{ndk_version}"

    externalNativeBuild {{
        cmake {{
            path = file("src/main/cpp/CMakeLists.txt")
        }}
    }}
''',
        1,
    )
else:
    import re
    text = re.sub(r'ndkVersion\s*=\s*"[^"]+"', f'ndkVersion = "{ndk_version}"', text, count=1)

if 'abiFilters += listOf("arm64-v8a")' not in text:
    marker = 'defaultConfig {'
    replacement = '''defaultConfig {
        ndk {
            abiFilters += listOf("arm64-v8a")
        }
'''
    text = text.replace(marker, replacement, 1)

path.write_text(text)
