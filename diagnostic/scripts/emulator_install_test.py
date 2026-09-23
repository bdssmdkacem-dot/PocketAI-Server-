#!/usr/bin/env python3
"""Run the x86_64 emulator install/launch diagnostic without multiline shell parsing."""

from pathlib import Path
import subprocess
import sys
import time

ROOT = Path.cwd()
DIAG = ROOT / "diagnostic" / "emulator"
DIAG.mkdir(parents=True, exist_ok=True)

PACKAGE = "com.pocketai.pocket_ai_server"
apk = ROOT / "build" / "app" / "outputs" / "flutter-apk" / "pocketai-flutter-smoke-x64.apk"
install_report = DIAG / "pocketai-flutter-smoke-x64-install.txt"
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
    "===== INSTALL TEST: Flutter x64 smoke APK =====\n"
    f"APK={apk}\n"
    f"APK_EXISTS={apk.is_file()}\n",
    encoding="utf-8",
)

if not apk.is_file():
    with install_report.open("a", encoding="utf-8") as f:
        f.write("INSTALL_COMMAND_ERROR=APK not found\nEXIT_CODE=126\n")
    print("Flutter x64 smoke APK not found", file=sys.stderr)
    sys.exit(0)

rc, output = run_capture(
    ["adb", "install", "-r", "-t", str(apk)],
    timeout=180,
)

with install_report.open("a", encoding="utf-8") as f:
    f.write(output)
    f.write(f"EXIT_CODE={rc}\n")
    f.write("--- PACKAGE MANAGER ---\n")
    pm_rc, pm_output = run_capture(
        ["adb", "shell", "pm", "path", PACKAGE],
        timeout=30,
    )
    f.write(pm_output)
    f.write(f"PM_PATH_RC={pm_rc}\n")
    f.write("--- POST-INSTALL DIAGNOSTICS ---\n")

    if rc == 0:
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
        f.write(f"COMMAND_RC={launch_rc}\n")

        time.sleep(5)

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
        ]

        with launch_report.open("w", encoding="utf-8") as lf:
            lf.write("===== LAUNCH TEST =====\n")
            lf.write(f"PACKAGE={PACKAGE}\n")
            lf.write("WAIT_AFTER_LAUNCH_SECONDS=5\n")
            for label, command in checks:
                check_rc, check_output = run_capture(command, timeout=60)
                lf.write(f"\n--- {label} ---\n")
                lf.write(check_output)
                lf.write(f"COMMAND_RC={check_rc}\n")

        log_rc, log_output = run_capture(
            ["adb", "logcat", "-d", "-v", "time", "-t", "1000"],
            timeout=60,
        )
        logcat_report.write_text(
            "===== LOGCAT AFTER FLUTTER SMOKE LAUNCH =====\n"
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
            f.write(f"PIDOF_AFTER_5S={pid_output.strip()!r}\n")
            f.write(f"PIDOF_RC={pid_rc}\n")
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
print(f"INSTALL_REPORT={install_report}")
print(f"LAUNCH_REPORT={launch_report}")
print(f"LOGCAT_REPORT={logcat_report}")
sys.exit(0)
