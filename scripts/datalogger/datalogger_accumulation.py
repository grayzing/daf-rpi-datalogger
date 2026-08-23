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
from rich import print

def log_info(message: str) -> None:
    print(f"[blue][INFO] [ACCUMULATION][/blue] {message}")

# Load config
with open("conf.yaml", "r") as file:
    config = yaml.safe_load(file)

sensor_addresses: list[int] = config["sensors"]["sensor_sdi12_addresses"]
soil_kpi_csv_path = config["sensors"]["buffer_csv_path"]
is_log_sensors = config["logging"]["log_sensors"]
sensor_query_periodicity_s: int = config["logging"]["sensor_periodicity_s"]

# Create the buffer if it doesn't exist
Path(soil_kpi_csv_path).touch(exist_ok=True)

assert len(sensor_addresses) > 0, "You have no sensor addresses configured in your conf.yaml!"

# soil_buffer_csv = pd.read_csv(soil_kpi_csv_path)

def get_sdi12_to_usb_port() -> serial.Serial | None:
    if is_log_sensors:
        log_info("Finding port for SDI12 <-> USB")
    ports = serial.tools.list_ports.comports()
    keywords = ["usb", "uart", "ftdi", "cp210", "ch34", "prolific"]
    
    for port in ports:
        description = port.description.lower()
        device = port.device
        
        # Check if the port description matches our hardware keywords
        if any(keyword in description for keyword in keywords):
            if is_log_sensors:
                log_info(f"Found candidate port: {device} ({port.description})")
            return serial.Serial(
                port=device,
                baudrate=9600,
                bytesize=8,
                parity="N")
    if is_log_sensors:
        log_info("No candidate port found!")
    return None

def check_sensor_sdi12_addresses(ser: serial.Serial | None) -> bool:
    assert ser is not None, "Invalid Serial"
    for address in sensor_addresses:
        cmd_measurement = f"{address}M!\r\n".encode('utf-8')
        cmd_data = f"{address}D0!\r\n".encode('utf-8')
        ser.write(cmd_measurement)
        time.sleep(2.1)
        ser.write(cmd_data)
        time.sleep(0.2)
        data_response = ser.read_all().decode('utf-8')
        assert data_response is not None, f"Sensor address {address} is not recognized on the SDI12 <-> USB adapter"
        return False

    return True

def accumulate_sensor_data(ser: serial.Serial | None) -> dict[int, list[list[float]]]:
    data_buffer: dict[int, list[list[float]]] = {}
    for address in sensor_addresses:
        data_buffer[address] = []
    assert ser is not None, "Invalid Serial"
    for address in sensor_addresses:
        temp_buffer = []
        cmd_measurement = f"{address}M!\r\n".encode('utf-8')
        cmd_data = f"{address}D0!\r\n".encode('utf-8')
        ser.write(cmd_measurement)
        time.sleep(2.1)
        ser.write(cmd_data)
        time.sleep(0.2)
        data_response = ser.read_all().decode('utf-8')
        processed_data_response = data_response.split('+')
        for data in processed_data_response:
            temp_buffer.append(float(data))
        data_buffer[address].append(temp_buffer)
    return data_buffer
            
if __name__ == "__main__":
    log_info("Pre-accumulation checks")
    ser = get_sdi12_to_usb_port()
    check_sensor_sdi12_addresses(ser)
    log_info("Starting accumulation loop")
    while True:
        time.sleep(sensor_query_periodicity_s)
        if is_log_sensors:
            log_info("Accumulating soil data!")
        accumulate_sensor_data(ser)
