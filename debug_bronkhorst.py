# -*- coding: utf-8 -*-
"""
This script connects to a Bronkhorst instrument, retrieves a list of all
supported parameters, and prints them to the console. This is useful for
debugging and finding the correct parameter numbers for a specific device.
"""

import propar
import sys

# We need serial.tools.list_ports to find the COM port.
try:
    import serial.tools.list_ports
except ImportError:
    print("Error: The 'pyserial' library is required to run this script.")
    print("Please install it by running: pip install pyserial")
    sys.exit(1)


def run_parameter_check():
    """
    Connects to the instrument and prints all known parameters.
    """
    # 1. Get a list of all available COM ports.
    available_ports = [port.device for port in serial.tools.list_ports.comports()]

    if not available_ports:
        print("Error: No COM ports found. Please ensure your device is connected.")
        return

    # 2. Ask the user to select a port from the list.
    print("Available COM ports:")
    for i, port in enumerate(available_ports):
        print(f"  {i}: {port}")

    try:
        selection = int(input("Enter the number of the port to connect to: "))
        selected_port = available_ports[selection]
    except (ValueError, IndexError):
        print("Invalid selection. Exiting.")
        return

    print(f"\nAttempting to connect to {selected_port}...")

    instrument = None
    try:
        # 3. Connect to the instrument.
        instrument = propar.instrument(selected_port)
        print(f"Successfully connected to {selected_port}.")

        # 4. NEW STRATEGY: Iterate through all possible parameter numbers (0-255)
        # and see which ones return a value. This is a robust way to find active parameters.

        print("\n--- Scanning for Active Parameters (0-255) ---")
        print(f"{'#':<10} | {'Current Value'}")
        print("-" * 30)

        found_params = 0
        for param_number in range(400):
            try:
                # Read the current value directly from the device.
                value = instrument.readParameter(param_number)

                # If the instrument returns a value (not None), it's an active parameter.
                if value is not None:
                    print(f"{param_number:<10} | {value}")
                    found_params += 1

            except Exception as e:
                # This can happen on some parameters, we can ignore it.
                # print(f"Error reading parameter {param_number}: {e}")
                pass

        print("-" * 30)
        print(f"Scan complete. Found {found_params} active parameters.")

        # --- NEW: Get specific device info for calculating absolute value ---
        print("\n--- Key Device Information ---")

        # Parameter 21 is typically 'Capacity' (the max value of the instrument's range)
        try:
            capacity = instrument.readParameter(21)
            if capacity is not None:
                print(f"Max Value (Capacity) [Parameter 21]: {capacity}")
            else:
                print("Could not read Capacity (Parameter 21).")
        except Exception as e:
            print(f"Error reading Parameter 21: {e}")

        # Parameter 129 is often the unit string
        try:
            unit = instrument.readParameter(129)
            if unit is not None:
                print(f"Programmed Unit [Parameter 129]:      {unit}")
            else:
                print("Could not read Unit (Parameter 129).")
        except Exception as e:
            print(f"Error reading Parameter 129: {e}")

        print("\nTo calculate the absolute value, use the formula:")
        print("Absolute Value = (Measure [Param 8] / 32000) * Max Value")
        print("---------------------------------")


    except Exception as e:
        print(f"\nAn error occurred: {e}")

    finally:
        # 5. Ensure the connection is always closed.
        # This is the correct shutdown command for this library version.
        if instrument:
            instrument.master.propar.stop()
            print("\nConnection closed.")


if __name__ == '__main__':
    run_parameter_check()

