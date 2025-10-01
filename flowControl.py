# -*- coding: utf-8 -*-
"""
Created on Wed Jun 21 15:26:36 2023

@author: SALLEJAUNE
"""

import propar
from PyQt5 import QtCore, uic
from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QInputDialog, QMessageBox
from PyQt5.QtGui import QIcon
import sys
import time
import qdarkstyle
from PyQt5.QtCore import Qt
import pathlib, os
from collections import deque

# --- New Feature: Auto-detect COM ports ---
# This requires the pyserial library. We'll check if it's installed.
try:
    import serial.tools.list_ports
except ImportError:
    # If pyserial is not installed, show an error message and exit.
    # A QApplication instance is needed to show a QMessageBox.
    app = QApplication(sys.argv)
    error_box = QMessageBox()
    error_box.setIcon(QMessageBox.Critical)
    error_box.setText("Required Library Missing")
    error_box.setInformativeText(
        "The 'pyserial' library is needed to detect COM ports.\n\n"
        "Please install it by running this command in your terminal:\n"
        "<b>pip install pyserial</b>"
    )
    error_box.setWindowTitle("Dependency Error")
    error_box.exec_()
    sys.exit(1)

# --- New Feature: Real-time plotting ---
# This requires the pyqtgraph library.
try:
    import pyqtgraph as pg
except ImportError:
    app = QApplication(sys.argv)
    error_box = QMessageBox()
    error_box.setIcon(QMessageBox.Critical)
    error_box.setText("Required Library Missing")
    error_box.setInformativeText(
        "The 'pyqtgraph' library is needed for plotting.\n\n"
        "Please install it by running this command in your terminal:\n"
        "<b>pip install pyqtgraph</b>"
    )
    error_box.setWindowTitle("Dependency Error")
    error_box.exec_()
    sys.exit(1)


class PlotWindow(QMainWindow):
    """
    This class creates a new window for plotting the pressure data in real-time.
    """

    def __init__(self, parent=None):
        super(PlotWindow, self).__init__(parent)
        self.setWindowTitle('Real-Time Pressure Plot')
        self.graphWidget = pg.PlotWidget()
        self.setCentralWidget(self.graphWidget)

        # Styling the plot
        self.graphWidget.setBackground('k')
        self.graphWidget.setTitle("Pressure Reading (%)", color="w", size="15pt")
        styles = {'color': 'w', 'font-size': '12pt'}
        self.graphWidget.setLabel('left', 'Pressure (%)', **styles)
        self.graphWidget.setLabel('bottom', 'Time (s)', **styles)
        self.graphWidget.showGrid(x=True, y=True)
        self.graphWidget.getAxis('bottom').setPen('w')
        self.graphWidget.getAxis('left').setPen('w')

        # Store the last 100 data points for plotting
        self.max_points = 100
        self.time_data = deque(maxlen=self.max_points)
        self.pressure_data = deque(maxlen=self.max_points)

        self.start_time = time.time()

        # Create a plot line with a yellow pen
        pen = pg.mkPen(color=(255, 255, 0), width=2)
        self.data_line = self.graphWidget.plot(list(self.time_data), list(self.pressure_data), pen=pen)

    def update_plot(self, pressure_value):
        """ This method is a slot that receives new data and updates the plot. """
        current_time = time.time() - self.start_time

        self.time_data.append(current_time)
        self.pressure_data.append(pressure_value)

        self.data_line.setData(list(self.time_data), list(self.pressure_data))

    def closeEvent(self, event):
        # Override closeEvent to only hide the window, not destroy it
        self.hide()
        event.ignore()


class Bronkhost(QMainWindow):

    def __init__(self, com='com4', name='XRL', parent=None):

        super(Bronkhost, self).__init__(parent)
        p = pathlib.Path(__file__)
        sepa = os.sep
        self.win = uic.loadUi('flow.ui', self)
        try:
            self.instrument = propar.instrument(com)
        except Exception as e:
            # If connection fails, show an error and close the app
            QMessageBox.critical(self, "Connection Error",
                                 f"Failed to connect to {com}.\n\nError: {e}\n\nPlease check the connection and try again.")
            # We need to exit cleanly. A timer is a safe way to close a window during __init__
            QtCore.QTimer.singleShot(0, self.close)
            return

        self.setWindowTitle(name)
        self.icon = str(p.parent) + sepa + 'icons' + sepa
        self.setWindowIcon(QIcon(self.icon + 'LOA.png'))
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.raise_()

        # Set valve to closed on startup
        self.instrument.writeParameter(12, 3)
        self.win.measure.setText('Valve closed')
        self.win.measure.setStyleSheet("color: red")
        # --- Initialize valve opening displays ---
        self.update_inlet_valve_display(0.0)

        self.closed = True
        self.actionButton()

        # --- Read device capacity and units ---
        self.capacity = 0.0
        self.unit = ""
        self.read_device_info()

        # --- Read initial PID settings from device ---
        self.read_pid_parameters()

        # --- Setup plot window and connect it ---
        self.plot_window = PlotWindow(self)
        self.threadFlow = THREADFlow(self)
        self.threadFlow.start()
        self.threadFlow.MEAS.connect(self.aff)
        self.threadFlow.VALVE1_MEAS.connect(self.update_inlet_valve_display)
        self.threadFlow.DEBUG_MEAS.connect(self.update_debug_display)  # Connect new debug signal
        self.threadFlow.MEAS.connect(self.plot_window.update_plot)

        self.win.title_2.setText(name + ' Flow Gas Control')

    def actionButton(self):
        self.win.openButton.clicked.connect(self.open)
        self.win.closeButton.clicked.connect(self.close)
        self.win.setpoint.editingFinished.connect(self.setPoint)
        self.win.dial.valueChanged.connect(self.dialMoved)

        # --- NEW: Connection for the Force Open button ---
        if hasattr(self.win, 'force_open_button'):
            self.win.force_open_button.clicked.connect(self.force_open)
        else:
            print("Warning: Could not find 'force_open_button' in UI. Manual override disabled.")
        if hasattr(self.win, 'scan_params'):
            self.win.scan_params.clicked.connect(self.run_parameter_check)

        if hasattr(self.win, 'plotButton'):
            self.win.plotButton.clicked.connect(self.show_plot_window)


        else:
            print("Warning: Could not find 'plotButton' in the UI. Plotting window will be unavailable.")

        if hasattr(self.win, 'set_pid_button'):
            self.win.set_pid_button.clicked.connect(self.set_pid_parameters)
        else:
            print("Warning: PID control widgets not found in UI. PID functionality disabled.")

    def run_parameter_check(self):

            instrument = self.instrument
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

    def read_device_info(self):
        """Reads the capacity and unit from the instrument to calculate absolute values."""
        try:
            capacity = self.instrument.readParameter(21)
            unit = self.instrument.readParameter(129)

            if capacity is not None:
                self.capacity = float(capacity)
                print(f"Device Capacity Read: {self.capacity}")
                # --- Configure the setpoint box's range and precision ---
                if hasattr(self.win, 'setpoint'):
                    self.win.setpoint.setMaximum(self.capacity)
                    self.win.setpoint.setDecimals(2)
            else:
                print("Warning: Could not read device capacity (param 21).")

            if unit is not None:
                self.unit = str(unit).strip()  # .strip() removes leading/trailing whitespace
                print(f"Device Unit Read: '{self.unit}'")
                # --- Set the dedicated unit label ---
                if hasattr(self.win, 'unit_label'):
                    self.win.unit_label.setText(self.unit)
                    # --- INCREASE FONT SIZE AND MAKE BOLD ---
                    self.win.unit_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: white;")
            else:
                print("Warning: Could not read device unit (param 129).")

        except Exception as e:
            print(f"Error reading device info: {e}")

    def read_pid_parameters(self):
        """Reads the current PID values from the instrument and updates the UI."""
        if not all(hasattr(self.win, w) for w in ['p_gain_box', 'i_gain_box', 'd_gain_box']):
            return  # Exit if the UI widgets don't exist
        try:
            # CORRECTED PID parameter numbers for this device model
            p_gain = self.instrument.readParameter(167)
            i_gain = self.instrument.readParameter(168)
            d_gain = self.instrument.readParameter(169)

            # Check if the returned value is not None before setting it in the UI
            if p_gain is not None:
                self.win.p_gain_box.setValue(p_gain)
            else:
                print("Warning: Failed to read P-gain parameter from instrument.")

            if i_gain is not None:
                self.win.i_gain_box.setValue(i_gain)
            else:
                print("Warning: Failed to read I-gain parameter from instrument.")

            if d_gain is not None:
                self.win.d_gain_box.setValue(d_gain)
            else:
                print("Warning: Failed to read D-gain parameter from instrument.")

            print(f"Read PID values: P={p_gain}, I={i_gain}, D={d_gain}")
        except Exception as e:
            print(f"Error reading PID parameters: {e}")

    def set_pid_parameters(self):
        """Writes the PID values from the UI to the instrument."""
        if not all(hasattr(self.win, w) for w in ['p_gain_box', 'i_gain_box', 'd_gain_box']):
            return  # Exit if the UI widgets don't exist
        try:
            p_gain = self.win.p_gain_box.value()
            i_gain = self.win.i_gain_box.value()
            d_gain = self.win.d_gain_box.value()

            # CORRECTED PID parameter numbers
            self.instrument.writeParameter(167, p_gain)  # Set P-action
            self.instrument.writeParameter(168, i_gain)  # Set I-action
            self.instrument.writeParameter(169, d_gain)  # Set D-action

            print(f"Set new PID values: P={p_gain}, I={i_gain}, D={d_gain}")
            QMessageBox.information(self, "Success", "PID parameters have been updated.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to set PID parameters.\n\nError: {e}")

    def show_plot_window(self):
        """ Shows the plot window when the button is clicked. """
        self.plot_window.show()


    def force_open(self):
        """DEBUG: Sends the 'Valve Fully Open' command to test hardware response."""
        print("Sending Force Open command (Mode 8)...")
        if hasattr(self.win, 'force_open_button'):
            self.win.force_open_button.setStyleSheet("background-color: blue;")
        self.win.openButton.setStyleSheet("background-color: gray;")
        self.win.closeButton.setStyleSheet("background-color: red;")  # Close is always an escape
        self.instrument.writeParameter(12, 8)  # 'Valve Fully Open' command
        self.closed = "Forced Open"

    def open(self):
        print('Valve control enabled')
        self.win.openButton.setStyleSheet("background-color: green")
        self.win.closeButton.setStyleSheet("background-color: gray")
        if hasattr(self.win, 'force_open_button'):
            self.win.force_open_button.setStyleSheet("background-color: gray;")
        self.instrument.writeParameter(12, 0)  # 'Setpoint Control' command
        self.closed = False
        self.win.measure.setStyleSheet("color: white")

    def close(self):
        print('Valve closed')
        self.win.closeButton.setStyleSheet("background-color: red")
        self.win.openButton.setStyleSheet("background-color: gray")
        if hasattr(self.win, 'force_open_button'):
            self.win.force_open_button.setStyleSheet("background-color: gray;")
        self.instrument.writeParameter(12, 3)  # 'Valve Closed' command
        self.closed = True
        self.win.measure.setStyleSheet("color: red")

        if hasattr(self.win, 'absolute_measure'):
            self.win.absolute_measure.setText("0.00")

    def setPoint(self):
        absolute_setpoint = self.win.setpoint.value()
        print(f"Absolute setpoint set to: {absolute_setpoint} {self.unit}")

        if self.capacity > 0:
            # Convert absolute setpoint to a percentage
            percentage = (absolute_setpoint / self.capacity) * 100.0

            # Clamp the percentage to be between 0 and 100
            percentage = max(0, min(100, percentage))

            self.win.dial.setValue(int(percentage))

            # Calculate raw Propar value from the percentage
            para = int(percentage * 32000 / 100)
            self.instrument.writeParameter(9, para)

            # --- Re-engage control mode every time setpoint changes ---
            if not self.closed:  # Only send if not in a closed state
                self.instrument.writeParameter(12, 0)  # 'Setpoint Control' command
        else:
            print("Warning: Cannot set point, device capacity is unknown or zero.")

    def dialMoved(self):
        percentage = self.win.dial.value()

        # Convert percentage from dial to an absolute value for the setpoint box
        if self.capacity > 0:
            absolute_value = (percentage / 100.0) * self.capacity
            # Use a non-blocking way to update the setpoint to avoid signal loops
            self.win.setpoint.blockSignals(True)
            self.win.setpoint.setValue(absolute_value)
            self.win.setpoint.blockSignals(False)

        # Calculate raw Propar value from the percentage
        para = int(percentage * 32000 / 100)
        self.instrument.writeParameter(9, para)

        # --- Re-engage control mode every time setpoint changes ---
        if not self.closed:  # Only send if not in a closed state
            self.instrument.writeParameter(12, 0)  # 'Setpoint Control' command

    def update_inlet_valve_display(self, raw_value):
        """Updates the inlet valve (param 11) display with the raw value from the thread."""
        if hasattr(self.win, 'inlet_valve_label'):
            # Display the raw integer value for debugging
            self.win.inlet_valve_label.setText(f"Raw: {int(raw_value)}")

    def update_debug_display(self, raw_value):
        """Updates the debug display with a raw value from the thread."""
        if hasattr(self.win, 'debug_param_output'):
            self.win.debug_param_output.setText(f"Raw: {int(raw_value)}")

    def aff(self, M):
        # This function updates the display with the measurement from the thread

        # This part updates always, regardless of valve state, to show pressure
        if self.capacity > 0:
            absolute_value = (float(M) / 100.0) * self.capacity
            if hasattr(self.win, 'absolute_measure'):
                self.win.absolute_measure.setText(f"{absolute_value:.2f}")

        # This part handles the state-specific text
        if self.closed == False:
            s_percent = float(M)
            # Use f-string formatting to always show two decimal places
            self.win.measure.setText(f"{s_percent:.2f}")

        elif self.closed is True:
            self.win.measure.setText('Valve closed')
        elif self.closed == "Forced Open":
            self.win.measure.setText('FORCED OPEN')

    def closeEvent(self, event):
        print("Closing application...")
        self.plot_window.close()
        self.threadFlow.stopThread()
        time.sleep(0.1)
        if hasattr(self, 'instrument'):
            self.instrument.writeParameter(12, 3)
            self.win.measure.setText('Valve closed')
            self.win.measure.setStyleSheet("color: red")
            time.sleep(0.5)
            # CORRECTED shutdown command
            self.instrument.master.propar.stop()
            print("Connection closed.")
        event.accept()


class THREADFlow(QtCore.QThread):
    MEAS = QtCore.pyqtSignal(float)
    VALVE1_MEAS = QtCore.pyqtSignal(float)  # Signal for inlet valve (param 11)
    DEBUG_MEAS = QtCore.pyqtSignal(float)  # --- NEW SIGNAL for debugging ---

    def __init__(self, parent):
        super(THREADFlow, self).__init__(parent)
        self.parent = parent
        self.instrument = self.parent.instrument
        self.stop = False

    def run(self):
        while not self.stop:
            try:
                # Read pressure measurement
                measure_value = float(self.instrument.readParameter(8) * 100 / 32000)
                self.MEAS.emit(measure_value)

                # Read inlet valve output
                valve1_output = self.instrument.readParameter(55)
                max_val=16777215

                if valve1_output is not None:
                    # Emit the raw value directly for debugging
                    norm=100*(100/61.5)
                    self.VALVE1_MEAS.emit(float(norm*(valve1_output/max_val)))


            except Exception as e:
                print(f"Error reading from instrument: {e}")
            time.sleep(0.5)
        print('Measurement thread stopped.')

    def stopThread(self):
        self.stop = True


if __name__ == '__main__':
    appli = QApplication(sys.argv)
    appli.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())

    available_ports = [port.device for port in serial.tools.list_ports.comports()]

    if not available_ports:
        QMessageBox.critical(None, "Connection Error", "No COM ports found. Please ensure your device is connected.")
        sys.exit()

    selected_port, ok = QInputDialog.getItem(
        None, "Select COM Port", "Connect to Bronkhorst device on:",
        available_ports, 0, False
    )

    if ok and selected_port:
        print(f"Attempting to connect to {selected_port}...")
        xuv = Bronkhost(com=selected_port)
        if hasattr(xuv, 'instrument'):
            xuv.show()
            appli.exec_()
    else:
        print("COM port selection cancelled. Exiting application.")
        sys.exit()

