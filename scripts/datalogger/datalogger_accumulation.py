"""
Gray Greenridge
GeNeLa
ggree024@ucr.edu

This script queries the SDI12 <-> USB adapter made by Dr. Liu
and saves sensor measurements to a .csv file.
"""

import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import serial
import serial.tools.list_ports
import yaml
from rich import print


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONFIG_PATH = "conf.yaml"


def load_config(config_path: str) -> dict:
    """Load and validate the YAML configuration."""
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            config = yaml.safe_load(file)

        if not config:
            raise ValueError("Configuration file is empty.")

        # Validate required configuration fields.
        sensors = config["sensors"]
        logging_config = config["logging"]

        required_sensor_fields = [
            "sensor_sdi12_addresses",
            "buffer_csv_path",
            "sensor_periodicity_s",
        ]

        for field in required_sensor_fields:
            if field not in sensors:
                raise KeyError(f"Missing configuration field: sensors.{field}")

        if "log_sensors" not in logging_config:
            raise KeyError("Missing configuration field: logging.log_sensors")

        return config

    except FileNotFoundError:
        print(f"[red]Configuration file '{config_path}' not found.[/red]")
        sys.exit(1)

    except yaml.YAMLError as e:
        print(f"[red]Could not parse '{config_path}': {e}[/red]")
        sys.exit(1)

    except (KeyError, ValueError, TypeError) as e:
        print(f"[red]Invalid configuration: {e}[/red]")
        sys.exit(1)


config = load_config(CONFIG_PATH)

sensor_addresses: list[int] = config["sensors"]["sensor_sdi12_addresses"]
soil_kpi_csv_path: str = config["sensors"]["buffer_csv_path"]
is_log_sensors: bool = bool(config["logging"]["log_sensors"])
sensor_query_periodicity_s: int = config["sensors"]["sensor_periodicity_s"]


# ---------------------------------------------------------------------------
# Serial Port
# ---------------------------------------------------------------------------

def get_sdi12_to_usb_port() -> serial.Serial | None:
    """Find and open the SDI-12 <-> USB adapter."""
    print("Finding port for SDI12 <-> USB")

    ports = serial.tools.list_ports.comports()

    for port in ports:
        # FTDI chip (VID 0x0403) = SDI-12 adapter
        if port.vid == 0x0403:
            print(
                f"Found candidate port: "
                f"{port.device} ({port.description})"
            )

            try:
                ser = serial.Serial(
                    port=port.device,
                    baudrate=9600,
                    bytesize=8,
                    parity="N",
                    timeout=2,
                )

                print(f"[green]Opened serial port {port.device}[/green]")
                return ser

            except serial.SerialException as e:
                print(
                    f"[red]Could not open {port.device}: {e}[/red]"
                )

    return None


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def initialize_csv(file_path: str) -> None:
    """Create the CSV file and write the header if necessary."""
    path = Path(file_path)

    try:
        # Ensure directory structure exists.
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write header if file is missing or empty.
        if not path.exists() or path.stat().st_size == 0:
            with open(
                path,
                mode="w",
                newline="",
                encoding="utf-8",
            ) as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp",
                    "sensor_address",
                    "volumetric_water_content_percent",
                    "soil_temperature_celsius",
                    "soil_permittivity",
                    "soil_bulk_ec_us_cm",
                    "raw_response",
                ])

            print(
                f"[green]Initialized new CSV at: {file_path}[/green]"
            )

    except OSError as e:
        print(
            f"[red]Could not initialize CSV '{file_path}': {e}[/red]"
        )
        sys.exit(1)


def save_measurement(
    file_path: str,
    address: int,
    volumetric_water_content_percent: float,
    soil_temperature_degrees_celsius: float,
    soil_permittivity: float,
    soil_bulk_ec: float,
    raw_decoded: str,
) -> bool:
    """Append one sensor measurement to the CSV."""
    try:
        timestamp = datetime.now().isoformat()

        with open(
            file_path,
            mode="a",
            newline="",
            encoding="utf-8",
        ) as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                address,
                volumetric_water_content_percent,
                soil_temperature_degrees_celsius,
                soil_permittivity,
                soil_bulk_ec,
                raw_decoded,
            ])

        return True

    except OSError as e:
        print(
            f"[red]Could not write measurement for sensor "
            f"{address} to CSV: {e}[/red]"
        )
        return False


# ---------------------------------------------------------------------------
# SDI-12
# ---------------------------------------------------------------------------

def query_sensor(ser: serial.Serial, address: int) -> str | None:
    """
    Query a sensor using M! followed by D0!.

    Returns:
        Decoded sensor response, or None if the query failed.
    """

    try:
        # Give the sensor a little time before issuing the command.
        time.sleep(1)

        # Flush stale serial data.
        ser.reset_input_buffer()

        # ---------------------------------------------------------------
        # Measurement command
        # ---------------------------------------------------------------

        m_command = f"{address}M!".encode("ascii")
        ser.write(m_command)
        ser.flush()

        # The adapter may return an acknowledgement followed by
        # additional information. Read until we receive something.
        m_response = ser.readline()

        if not m_response:
            print(
                f"[yellow]Sensor {address}: "
                f"no response to M! command.[/yellow]"
            )
            return None

        # ---------------------------------------------------------------
        # Data command
        # ---------------------------------------------------------------

        d_command = f"{address}D0!".encode("ascii")
        ser.write(d_command)
        ser.flush()

        d_response = ser.readline()

        if not d_response:
            print(
                f"[yellow]Sensor {address}: "
                f"no response to D0! command.[/yellow]"
            )
            return None

        # Remove CR/LF.
        d_response = d_response.rstrip(b"\r\n")

        try:
            raw_decoded = d_response.decode("ascii")
        except UnicodeDecodeError:
            raw_decoded = d_response.decode("utf-8", errors="replace")

        if not raw_decoded:
            print(
                f"[yellow]Sensor {address}: "
                f"received an empty response.[/yellow]"
            )
            return None

        return raw_decoded

    except serial.SerialTimeoutException as e:
        print(
            f"[yellow]Sensor {address}: serial timeout: {e}[/yellow]"
        )
        return None

    except serial.SerialException as e:
        print(
            f"[red]Serial communication error while querying "
            f"sensor {address}: {e}[/red]"
        )
        return None


def parse_sensor_response(
    raw_decoded: str,
    address: int,
) -> tuple[float, float, float, float] | None:
    """Parse the SDI-12 sensor response."""

    try:
        # SDI-12 values are separated by '+' or '-'.
        #
        # For example:
        # 0+12.34+23.45+4.56+78.90
        #
        # split("+") is intentionally retained here because the
        # expected sensor payload uses positive values.

        split_sensor_data = raw_decoded.split("+")

        if len(split_sensor_data) < 5:
            raise ValueError(
                f"Expected at least 5 fields, got "
                f"{len(split_sensor_data)}"
            )

        volumetric_water_content_percent = float(
            split_sensor_data[1]
        )

        soil_temperature_degrees_celsius = float(
            split_sensor_data[2]
        )

        soil_permittivity = float(
            split_sensor_data[3]
        )

        soil_bulk_ec = float(
            split_sensor_data[4]
        )

        return (
            volumetric_water_content_percent,
            soil_temperature_degrees_celsius,
            soil_permittivity,
            soil_bulk_ec,
        )

    except (ValueError, IndexError) as e:
        print(
            f"[red]Error parsing payload from sensor {address} "
            f"('{raw_decoded}'): {e}[/red]"
        )
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    initialize_csv(soil_kpi_csv_path)

    ser = get_sdi12_to_usb_port()

    if ser is None:
        print(
            "[red]No candidate port found. "
            "Is the SDI-12 to USB adapter receiving power?[/red]"
        )
        sys.exit(1)

    # Delay for Arduino bootloader and adapter initialization.
    time.sleep(2.5)

    print(
        "[green]Starting measurement accumulation loop...[/green]"
    )

    try:
        while True:

            # Check whether the serial connection is still alive.
            if not ser.is_open:
                print(
                    "[yellow]Serial port is closed. "
                    "Attempting to reconnect...[/yellow]"
                )

                ser = get_sdi12_to_usb_port()

                if ser is None:
                    print(
                        "[yellow]Could not reconnect. "
                        "Retrying in 10 seconds...[/yellow]"
                    )
                    time.sleep(10)
                    continue

            for address in sensor_addresses:

                # -------------------------------------------------------
                # Query sensor
                # -------------------------------------------------------

                raw_decoded = query_sensor(ser, address)

                if raw_decoded is None:
                    print(
                        f"[yellow]Skipping sensor {address} "
                        f"for this measurement cycle.[/yellow]"
                    )
                    continue

                print(
                    f"Sensor reading for sensor with address "
                    f"{address}: {raw_decoded}"
                )

                # -------------------------------------------------------
                # Parse response
                # -------------------------------------------------------

                parsed_data = parse_sensor_response(
                    raw_decoded,
                    address,
                )

                if parsed_data is None:
                    # Parsing failed, but the logger itself should
                    # continue to the next sensor.
                    continue

                (
                    volumetric_water_content_percent,
                    soil_temperature_degrees_celsius,
                    soil_permittivity,
                    soil_bulk_ec,
                ) = parsed_data

                # -------------------------------------------------------
                # Save measurement
                # -------------------------------------------------------

                if is_log_sensors:
                    success = save_measurement(
                        soil_kpi_csv_path,
                        address,
                        volumetric_water_content_percent,
                        soil_temperature_degrees_celsius,
                        soil_permittivity,
                        soil_bulk_ec,
                        raw_decoded,
                    )

                    if success:
                        print(
                            f"[blue]Successfully saved measurement "
                            f"for address {address} to CSV.[/blue]"
                        )

            # Wait before starting the next measurement cycle.
            time.sleep(sensor_query_periodicity_s)

    except KeyboardInterrupt:
        print("\n[yellow]Measurement loop stopped by user.[/yellow]")

    except Exception as e:
        # Catch unexpected errors so that they are clearly reported.
        # This is deliberately the last-resort handler.
        print(
            f"[red]Unexpected fatal error: {type(e).__name__}: {e}[/red]"
        )

    finally:
        if ser is not None and ser.is_open:
            ser.close()
            print("[green]Serial port closed.[/green]")


if __name__ == "__main__":
    main()
