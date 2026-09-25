#!/usr/bin/env python3
"""Run the x86_64 emulator install/launch diagnostic without multiline shell parsing."""

from pathlib import Path
import json
import subprocess
import sys
import time

ROOT = Path.cwd()
DIAG = ROOT / "diagnostic" / "emulator"
DIAG.mkdir(parents=True, exist_ok=True)

PACKAGE = "com.pocketai.pocket_ai_server"
apk = ROOT / "build" / "app" / "outputs" / "flutter-apk" / "pocketai-native-x64.apk"
install_report = DIAG / "pocketai-native-x64-install.txt"
device_report = DIAG / "device.txt"
launch_report = DIAG / "launch.txt"
logcat_report = DIAG / "launch-logcat.txt"


def run_capture(cmd, timeout=60):
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        )
        return p.returncode, p.stdout
    except subprocess.TimeoutExpired:
        return 124, f"COMMAND_TIMEOUT={timeout}s\n"
    except Exception as exc:
        return 125, f"COMMAND_ERROR={exc!r}\n"


device_commands = [
    ["adb", "shell", "getprop", "ro.product.manufacturer"],
    ["adb", "shell", "getprop", "ro.product.model"],
    ["adb", "shell", "getprop", "ro.build.version.release"],
    ["adb", "shell", "getprop", "ro.build.version.sdk"],
    ["adb", "shell", "getprop", "ro.product.cpu.abilist"],
]

with device_report.open("w", encoding="utf-8") as f:
    f.write("=== EMULATOR ===\n")
    for cmd in device_commands:
        rc, output = run_capture(cmd)
        f.write(output)
        if rc != 0:
            f.write(f"COMMAND_RC={rc}\n")

install_report.write_text(
    "===== INSTALL TEST: Native x64 runtime APK =====\n"
    f"APK={apk}\n"
    f"APK_EXISTS={apk.is_file()}\n",
    encoding="utf-8",
)

if not apk.is_file():
    with install_report.open("a", encoding="utf-8") as f:
        f.write("INSTALL_COMMAND_ERROR=APK not found\nEXIT_CODE=126\n")
    print("Native x64 runtime APK not found", file=sys.stderr)
    sys.exit(0)

rc, output = run_capture(
    ["adb", "install", "-r", "-t", str(apk)],
    timeout=180,
)

# Android's package manager can finish an install after the adb client times out.
# Therefore pm path is authoritative for whether the package is actually present.
pm_rc, pm_output = run_capture(
    ["adb", "shell", "pm", "path", PACKAGE],
    timeout=30,
)
installed = pm_rc == 0 and any(
    line.strip().startswith("package:") for line in pm_output.splitlines()
)
effective_install = rc == 0 or installed

with install_report.open("a", encoding="utf-8") as f:
    f.write(output)
    f.write(f"INSTALL_COMMAND_RC={rc}\n")
    f.write(f"INSTALL_COMMAND_TIMEOUT={rc == 124}\n")
    f.write(f"INSTALL_VERIFIED_BY_PM={installed}\n")
    f.write(f"INSTALL_VERIFIED={effective_install}\n")
    f.write("--- PACKAGE MANAGER ---\n")
    f.write(pm_output)
    f.write(f"PM_PATH_RC={pm_rc}\n")
    f.write("--- POST-INSTALL DIAGNOSTICS ---\n")

    if effective_install:
        f.write("\n$ adb shell dumpsys package " + PACKAGE + "\n")
        cmd_rc, cmd_output = run_capture(
            ["adb", "shell", "dumpsys", "package", PACKAGE],
            timeout=60,
        )
        f.write(cmd_output)
        f.write(f"COMMAND_RC={cmd_rc}\n")

        # Clear old app logs, launch, then give Flutter enough time to initialize.
        run_capture(["adb", "logcat", "-c"], timeout=30)

        f.write("\n$ adb shell monkey -p " + PACKAGE + " 1\n")
        launch_rc, launch_output = run_capture(
            ["adb", "shell", "monkey", "-p", PACKAGE, "1"],
            timeout=60,
        )
        f.write(launch_output)
        f.write(f"LAUNCH_RC={launch_rc}\n")

        # The emulator is heavily loaded, so allow extra time for Flutter startup.
        time.sleep(10)

        checks = [
            ("PIDOF", ["adb", "shell", "pidof", PACKAGE]),
            (
                "ACTIVITY",
                ["adb", "shell", "dumpsys", "activity", "activities"],
            ),
            (
                "PACKAGE_STATE",
                ["adb", "shell", "dumpsys", "package", PACKAGE],
            ),
            (
                "UI_DUMP",
                ["adb", "shell", "uiautomator", "dump", "/sdcard/pocketai-ui.xml"],
            ),
            (
                "UI_TEXT",
                ["adb", "shell", "cat", "/sdcard/pocketai-ui.xml"],
            ),
        ]

        with launch_report.open("w", encoding="utf-8") as lf:
            lf.write("===== LAUNCH TEST =====\n")
            lf.write(f"PACKAGE={PACKAGE}\n")
            lf.write("WAIT_AFTER_LAUNCH_SECONDS=10\n")
            for label, command in checks:
                check_rc, check_output = run_capture(command, timeout=60)
                lf.write(f"\n--- {label} ---\n")
                lf.write(check_output)
                lf.write(f"COMMAND_RC={check_rc}\n")

        # Verify the localhost OpenAI-compatible HTTP API through adb port forwarding.
        http_report = DIAG / "http-api.txt"
        forward_rc, forward_output = run_capture(["adb", "forward", "tcp:18080", "tcp:8080"], timeout=30)
        http_verified = False
        if forward_rc == 0:
            try:
                from urllib.error import HTTPError
                from urllib.request import Request, urlopen

                base = "http://127.0.0.1:18080"

                def http_get(path):
                    with urlopen(base + path, timeout=3) as response:
                        return response.status, json.loads(response.read().decode())

                health = None
                for _ in range(30):
                    try:
                        status, health = http_get("/health")
                        if status == 200 and health.get("status") == "ok":
                            break
                    except Exception:
                        time.sleep(1)
                else:
                    raise RuntimeError("HTTP /health did not become ready")

                assert health.get("native_ready") is True, health
                assert health.get("model_loaded") is False, health
                model_status, models = http_get("/v1/models")
                assert model_status == 200, model_status
                assert models.get("object") == "list", models
                assert models.get("data") == [], models

                payload = json.dumps({
                    "model": "none",
                    "messages": [{"role": "user", "content": "hello"}],
                }).encode()
                request = Request(
                    base + "/v1/chat/completions",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    urlopen(request, timeout=3)
                    raise AssertionError("Expected HTTP 409 when no model is loaded")
                except HTTPError as error:
                    assert error.code == 409, error.code
                    error_body = json.loads(error.read().decode())
                    assert "error" in error_body, error_body

                http_verified = True
                http_report.write_text(
                    "HTTP_SERVER_VERIFICATION=PASSED\\n"
                    f"HEALTH={health}\\n"
                    f"MODELS={models}\\n"
                    f"CHAT_NO_MODEL={error_body}\\n",
                    encoding="utf-8",
                )
                print("HTTP_SERVER_VERIFICATION=PASSED")
            except Exception as exc:
                http_report.write_text(
                    "HTTP_SERVER_VERIFICATION=FAILED\\n"
                    f"ERROR={exc!r}\\n",
                    encoding="utf-8",
                )
                print(f"HTTP_SERVER_VERIFICATION=FAILED: {exc}", file=sys.stderr)
        else:
            http_report.write_text(
                "HTTP_SERVER_VERIFICATION=FAILED\\n"
                f"ADB_FORWARD_RC={forward_rc}\\n"
                f"{forward_output}",
                encoding="utf-8",
            )
        run_capture(["adb", "forward", "--remove", "tcp:18080"], timeout=30)

        log_rc, log_output = run_capture(
            ["adb", "logcat", "-d", "-v", "time", "-t", "1000"],
            timeout=60,
        )
        logcat_report.write_text(
            "===== LOGCAT AFTER NATIVE x64 LAUNCH =====\n"
            + log_output
            + f"\nLOGCAT_COMMAND_RC={log_rc}\n",
            encoding="utf-8",
        )

        with install_report.open("a", encoding="utf-8") as f:
            f.write("\n--- LAUNCH SUMMARY ---\n")
            pid_rc, pid_output = run_capture(
                ["adb", "shell", "pidof", PACKAGE],
                timeout=30,
            )
            f.write(f"PIDOF_AFTER_10S={pid_output.strip()!r}\n")
            f.write(f"PIDOF_RC={pid_rc}\n")
            ui_rc, ui_output = run_capture(
                ["adb", "shell", "cat", "/sdcard/pocketai-ui.xml"],
                timeout=30,
            )
            native_ready = "Native Ready" in ui_output
            runtime_ok = "OK;backend_initialized;version=" in ui_output
            f.write(f"NATIVE_READY_IN_UI={native_ready}\n")
            f.write(f"RUNTIME_CHECK_OK_IN_UI={runtime_ok}\n")
            f.write(f"UI_TEXT_RC={ui_rc}\n")
            if not (pid_rc == 0 and pid_output.strip() and native_ready and runtime_ok):
                f.write("NATIVE_RUNTIME_VERIFICATION=FAILED\n")
            else:
                f.write("NATIVE_RUNTIME_VERIFICATION=PASSED\n")
    else:
        log_rc, log_output = run_capture(
            ["adb", "shell", "logcat", "-d", "-v", "time", "-t", "500"],
            timeout=60,
        )
        f.write("\n--- INSTALL FAILURE LOGCAT ---\n")
        f.write(log_output)
        f.write(f"COMMAND_RC={log_rc}\n")

(DIAG / "arm64-install-skipped.txt").write_text(
    "ARM64 native APK is intentionally not installed on the x86_64 emulator.\n"
    "The ARM64 APK is the target for the physical ARM64 Android device.\n",
    encoding="utf-8",
)
(DIAG / "INSTALL_TESTS_COMPLETED.txt").write_text(
    "INSTALL_TESTS_COMPLETED=1\n",
    encoding="utf-8",
)

print(f"FLUTTER_X64_INSTALL_RC={rc}")
print(f"INSTALL_VERIFIED={effective_install}")
print(f"INSTALL_REPORT={install_report}")
print(f"LAUNCH_REPORT={launch_report}")
runtime_verified = False
if install_report.is_file():
    report_text = install_report.read_text(encoding="utf-8")
    runtime_verified = "NATIVE_RUNTIME_VERIFICATION=PASSED" in report_text

print(f"LOGCAT_REPORT={logcat_report}")
print(f"NATIVE_RUNTIME_VERIFICATION={runtime_verified}")
sys.exit(0 if (effective_install and runtime_verified and http_verified) else 1)
