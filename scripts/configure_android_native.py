from pathlib import Path

path = Path("android/app/build.gradle.kts")
text = path.read_text()

if 'externalNativeBuild {' not in text:
    text = text.replace(
        'android {',
        '''android {
    ndkVersion = "27.2.12479018"

    externalNativeBuild {
        cmake {
            path = file("src/main/cpp/CMakeLists.txt")
        }
    }
''',
        1,
    )

if 'abiFilters += listOf("arm64-v8a")' not in text:
    marker = 'defaultConfig {'
    replacement = '''defaultConfig {
        ndk {
            abiFilters += listOf("arm64-v8a")
        }
'''
    text = text.replace(marker, replacement, 1)

path.write_text(text)
