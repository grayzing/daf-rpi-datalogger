"""
Gray Greenridge
GeNeLa
2026

This is where the datalogger accumulates sensor readings.
"""

import subprocess
import serial.tools.list_ports
import serial
import time
import pandas as pd
import yaml
from pathlib import Path

# Load config
with open("conf.yaml", "r") as file:
    config = yaml.safe_load(file)

sensor_addresses: list[int] = config["sensors"]["sensor_sdi12_addresses"]
soil_kpi_csv_path = config["sensors"]["buffer_csv_path"]

# Create the buffer if it doesn't exist
Path(soil_kpi_csv_path).touch(exist_ok=True)

assert len(sensor_addresses) > 0, "You have no sensor addresses configured in your conf.yaml!"

soil_buffer_csv = pd.read_csv(soil_kpi_csv_path)

def get_sdi12_to_usb_port():
    pass

if __name__ == "__main__":
    while True:
        pass
