"""
Gray Greenridge
GeNeLa
2026

This script runs on the datalogger. There are two components.
"""

import subprocess
import yaml
import time

# Load config
with open("conf.yaml", "r") as file:
    config = yaml.safe_load(file)

ap_ssid = config["networking"]["ap_ssid"]
ap_pw = config["networking"]["ap_pw"]
ap_scan_interval: float = config["networking"]["ap_scan_interval"]


def find_ap():
    """Return the signal strength of the target AP, or None."""

    result = subprocess.run(
        ["nmcli", "-t", "-f", "SSID,SIGNAL", "device", "wifi", "list"],
        capture_output=True,
        text=True,
        check=True
    )

    for line in result.stdout.splitlines():
        if not line:
            continue

        # SSIDs can technically contain ':', so split from the right.
        ssid, signal = line.rsplit(":", 1)

        if ssid == ap_ssid:
            return int(signal)

    return None


def connect():
    print(f"Connecting to {ap_ssid}...")

    result = subprocess.run(
        [
            "nmcli",
            "device",
            "wifi",
            "connect",
            ap_ssid,
            "password",
            ap_pw,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print("Connected!")
        return True

    print("Connection failed:")
    print(result.stderr.strip())
    return False


def main():
    print(f"Waiting for AP: {ap_ssid}")

    while True:
        signal = find_ap()

        if signal is None:
            print("AP not detected")
        else:
            print(f"AP detected, signal = {signal}%")
            connect()

        time.sleep(ap_scan_interval)


if __name__ == "__main__":
    main()