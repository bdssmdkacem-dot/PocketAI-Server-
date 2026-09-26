#!/usr/bin/env python3
"""Build PocketAI's native runtime for every Flutter-supported Android ABI."""

from pathlib import Path
import os
import shutil
import subprocess
import sys

ROOT = Path.cwd()
NDK = Path(os.environ.get("ANDROID_NDK", ""))
if not NDK.is_dir():
    raise SystemExit("ANDROID_NDK is not set to a valid NDK directory.")

CMAKE_FILE = ROOT / "android" / "app" / "src" / "main" / "cpp" / "CMakeLists.txt"
JNI_ROOT = ROOT / "android" / "app" / "src" / "main" / "jniLibs"

ABIS = ("armeabi-v7a", "arm64-v8a", "x86_64")
JNI_SYMBOLS = (
    "Java_com_pocketai_pocket_1ai_1server_NativeAi_isReady",
    "Java_com_pocketai_pocket_1ai_1server_NativeAi_status",
    "Java_com_pocketai_pocket_1ai_1server_NativeAi_version",
    "Java_com_pocketai_pocket_1ai_1server_NativeAi_runtimeCheck",
    "Java_com_pocketai_pocket_1ai_1server_NativeAi_loadModel",
    "Java_com_pocketai_pocket_1ai_1server_NativeAi_unloadModel",
    "Java_com_pocketai_pocket_1ai_1server_NativeAi_isModelLoaded",
    "Java_com_pocketai_pocket_1ai_1server_NativeAi_loadedModelName",
    "Java_com_pocketai_pocket_1ai_1server_NativeAi_generate",
)

REQUIRED_LIBS = (
    "libpocket_ai.so",
    "libllama.so",
    "libggml.so",
    "libggml-base.so",
    "libggml-cpu.so",
)


def run(*args: str) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> None:
    if not CMAKE_FILE.is_file():
        raise SystemExit(f"Missing native CMake file: {CMAKE_FILE}")

    if JNI_ROOT.exists():
        shutil.rmtree(JNI_ROOT)
    JNI_ROOT.mkdir(parents=True)

    for abi in ABIS:
        build_dir = Path("/tmp") / f"pocketai-cmake-{abi}"
        if build_dir.exists():
            shutil.rmtree(build_dir)

        print(f"=== Native build: {abi} ===", flush=True)
        run(
            "cmake",
            "-S",
            str(CMAKE_FILE.parent),
            "-B",
            str(build_dir),
            f"-DCMAKE_TOOLCHAIN_FILE={NDK / 'build/cmake/android.toolchain.cmake'}",
            f"-DANDROID_ABI={abi}",
            "-DANDROID_PLATFORM=android-24",
            "-DCMAKE_BUILD_TYPE=Release",
            "-DGGML_NATIVE=OFF",
            "-DGGML_OPENMP=OFF",
            "-DGGML_LLAMAFILE=OFF",
            "-DLLAMA_OPENSSL=OFF",
        )
        run(
            "cmake",
            "--build",
            str(build_dir),
            "--target",
            "pocket_ai",
            "--parallel",
            "2",
        )

        out_dir = build_dir / "bin"
        pocket = build_dir / "libpocket_ai.so"
        if not pocket.is_file():
            raise SystemExit(f"{abi}: missing {pocket}")

        target_dir = JNI_ROOT / abi
        target_dir.mkdir(parents=True)

        produced = [pocket]
        for name in REQUIRED_LIBS[1:]:
            candidate = out_dir / name
            if not candidate.is_file():
                raise SystemExit(f"{abi}: missing dependency {candidate}")
            produced.append(candidate)

        for source in produced:
            destination = target_dir / source.name
            shutil.copy2(source, destination)
            print("PACKAGED", destination, flush=True)

        run("file", *[str(target_dir / name) for name in REQUIRED_LIBS])
        symbols = subprocess.check_output(
            ["readelf", "-Ws", str(target_dir / "libpocket_ai.so")],
            text=True,
        )
        for symbol in JNI_SYMBOLS:
            if symbol not in symbols:
                raise SystemExit(f"{abi}: missing JNI export {symbol}")
        print(f"{abi}: JNI exports OK", flush=True)

    print("=== Native ABI matrix ===", flush=True)
    for abi in ABIS:
        for name in REQUIRED_LIBS:
            path = JNI_ROOT / abi / name
            if not path.is_file() or path.stat().st_size == 0:
                raise SystemExit(f"Missing or empty packaged library: {path}")
        print(f"{abi}: OK", flush=True)


if __name__ == "__main__":
    main()
