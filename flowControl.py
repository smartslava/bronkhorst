# -*- coding: utf-8 -*-
"""
Created on Wed Jun 21 15:26:36 2023
@author: SALLEJAUNE & Slava Smartsev
"""
__version__ = "1.1.0"

from admin_window import AdminWindow
from help_window import HelpWindow
import propar
from PyQt5 import QtCore, uic
from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QInputDialog, QMessageBox, QLineEdit

from PyQt5.QtGui import QIcon
import sys
import time
import qdarkstyle
from PyQt5.QtCore import Qt
import pathlib, os
from collections import deque
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
# --- Auto-detect COM ports ---

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

# --- Real-time plotting ---
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
from PyQt5.QtWidgets import QDoubleSpinBox
from PyQt5.QtCore import Qt, QTimer

def calculate_valve_percentage(raw_valve_output):
    """Converts the raw valve output (param 55) to a percentage."""
    max_val = 16777215
    norm = 100 * (100 / 61.67)
    return float(norm * (raw_valve_output / max_val))

class Stream(QtCore.QObject):
    """Redirects console output to a QTextEdit widget."""
    new_text = QtCore.pyqtSignal(str)

    def write(self, text):
        self.new_text.emit(str(text))

    def flush(self):
        # This is needed for compatibility.
        pass

class EnterSpinBox(QDoubleSpinBox):
    """
    A custom QDoubleSpinBox that clears the text selection after
    the user presses the Enter key.
    """
    def __init__(self, parent=None):
        super(EnterSpinBox, self).__init__(parent)

    def keyPressEvent(self, event):
        # First, let the original QDoubleSpinBox handle the key press
        super(EnterSpinBox, self).keyPressEvent(event)

        # Now, check if the key that was just pressed was Enter or Return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # QTimer.singleShot(0, ...) waits until the current event is
            # finished and then runs our command. This is necessary because
            # the selection happens immediately after our event runs.
            QTimer.singleShot(0, self.lineEdit().deselect)

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
        self.graphWidget.setTitle("Pressure Reading (bar)", color="w", size="15pt")
        styles = {'color': 'w', 'font-size': '12pt'}
        self.graphWidget.setLabel('left', 'Pressure (bar)', **styles)
        self.graphWidget.setLabel('bottom', 'Time (s)', **styles)
        self.graphWidget.showGrid(x=True, y=True)
        self.graphWidget.getAxis('bottom').setPen('w')
        self.graphWidget.getAxis('left').setPen('w')

        # Store the last 500 data points for plotting
        self.max_points = 200
        self.time_data = deque(maxlen=self.max_points)
        self.pressure_data = deque(maxlen=self.max_points)
        self.setpoint_data = deque(maxlen=self.max_points)  # History of the setpoint
        self.start_time = time.monotonic()

        # Create a plot line with a yellow pen
        pen = pg.mkPen(color=(255, 255, 0), width=2)
        self.data_line = self.graphWidget.plot(list(self.time_data), list(self.pressure_data), pen=pen)

        # 1. Create the setpoint line item (initially empty)
        setpoint_pen = pg.mkPen(color=(255, 0, 0), width=1.5)  # Red, 1px thickness
        self.setpoint_line = self.graphWidget.plot(pen=setpoint_pen)
        # 2. Store the current setpoint value
        self.current_setpoint = 0.0

    def set_setpoint_value(self, value):
        """A simple slot to receive and store the current setpoint value."""
        self.current_setpoint = value

    def update_plot(self, timestamp, pressure_value):
        """ This method is a slot that receives new data and updates the plot. """
        elapsed_time = timestamp - self.start_time
        self.time_data.append(elapsed_time)
        self.pressure_data.append(pressure_value)
        self.setpoint_data.append(self.current_setpoint)
        self.data_line.setData(list(self.time_data), list(self.pressure_data))

        # Ensure there's data to draw a line across
        if self.time_data:
            # Get the start and end times of the current data window
            x_start = self.time_data[0]
            x_end = self.time_data[-1]

            # Draw a horizontal line from the start to the end at the setpoint value
            #self.setpoint_line.setData([x_start, x_end], [self.current_setpoint, self.current_setpoint])
            self.setpoint_line.setData(list(self.time_data), list(self.setpoint_data))

    def closeEvent(self, event):
        # Override closeEvent to only hide the window, not destroy it
        self.hide()
        event.ignore()


class Bronkhost(QMainWindow):

    def __init__(self, com=None, name=None, parent=None):
        if com is None:
            # If no port was given, maybe pop up the selection dialog right here!
            # Or print an error, etc.
            print("Error: No COM port was provided.")
            return  # Stop initialization

        super(Bronkhost, self).__init__(parent)
        self.is_offline = False
        self.connection_successful = False
        p = pathlib.Path(__file__)
        sepa = os.sep
        self.win = uic.loadUi('flow.ui', self)
        self.win.setpoint.setGroupSeparatorShown(False)

        #-----Flickering Label-----------
        self.flicker_timer = QTimer(self)
        self.flicker_timer.timeout.connect(self._toggle_status_label_visibility)
        self.label_is_visible = True  # State tracker for the flicker

        # --- REDIRECT PRINT STATEMENTS ---
        # 1. Create an instance of our custom stream
        self.log_stream = Stream()
        # 2. Connect the stream's signal to our update function
        self.log_stream.new_text.connect(self.update_log)
        # 3. Redirect Python's standard output to our custom stream
        sys.stdout = self.log_stream
        print(f"--- LOA Pressure Control v{__version__} ---")
        # ------------------------------------
        try:
            self.instrument = propar.instrument(com)
            device_serial = self.instrument.readParameter(1)  # Try to read the serial number
            if device_serial is None:
                raise ConnectionError("Device is not responding on this port.")
            print(f"Successfully connected to device with serial number: {device_serial}")
            self.connection_successful = True

            print("Reading initial device status...")
            initial_status = self.instrument.readParameter(28)
            if initial_status is not None:
                binary_string = bin(initial_status)[2:].zfill(8)
                print(f"Initial device status (param 28): Value={initial_status}, Bits={binary_string}")
            else:
                print("Could not read initial device status.")

        except Exception as e:
            # If connection fails, show an error
            print("Failed")
            QMessageBox.critical(self, "Connection Error",
                                 f"Failed to connect to {com}.\n\nError: {e}\n\nPlease check connection or try another port.")

            return

        self.setWindowTitle(f"{name} v{__version__}")
        self.icon = str(p.parent) + sepa + 'icons' + sepa
        self.setWindowIcon(QIcon(self.icon + 'LOA3.png'))
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.raise_()

        # Set valve to closed on startup
        self.actionButton()
        self.valve_close()

        # --- Read device capacity and units ---
        self.capacity = 0.0
        self.unit = ""
        self.read_device_info()

        # Read initial setpoint from device and update UI ---
        self.plot_window = PlotWindow(self)
        self.read_initial_setpoint()
        self.threadFlow = THREADFlow(self, capacity=self.capacity)

        self.threadFlow.start()
        self.threadFlow.MEAS.connect(self.aff)
        self.threadFlow.VALVE1_MEAS.connect(self.update_inlet_valve_display)
        self.threadFlow.DEBUG_MEAS.connect(self.update_debug_display)  # Connect new debug signal
        self.threadFlow.MEAS.connect(self.plot_window.update_plot)
        self.threadFlow.DEVICE_STATUS_UPDATE.connect(self.update_device_status)

        self.win.title_2.setText('Pressure Control')

    def update_device_status(self, status):
        """Updates the device status label and enables/disables controls."""
        if not hasattr(self.win, 'device_status_label'):
            return

        if status == 'offline':
            if not self.is_offline:
                print("Connection to device lost...")
                self.is_offline = True
            # --- OFFLINE STATE: Gray out and disable UI elements ---
            self.win.device_status_label.setText('Offline')
            self.win.device_status_label.setStyleSheet("color: red; font-weight: bold;")

            self.flicker_timer.stop()
            self.win.label_valve_status.setText("...")
            self.win.label_valve_status.setStyleSheet("color: gray;")

            self.win.measure.setText("...")
            self.win.inlet_valve_label.setText("...")

            self.win.plotButton.setEnabled(False)
            self.win.openButton.setEnabled(False)
            self.win.closeButton.setEnabled(False)
            self.win.setpoint.setEnabled(False)
            if hasattr(self.win, 'admin_button'):
                self.win.admin_button.setEnabled(False)

            # Set a uniform gray style for all affected widgets
            self.win.openButton.setStyleSheet("background-color: gray;")
            self.win.closeButton.setStyleSheet("background-color: gray;")
            self.win.plotButton.setStyleSheet("background-color: gray;")

            gray_text_style = "color: gray;"
            if hasattr(self.win, 'setpoint_label'): self.win.setpoint_label.setStyleSheet(gray_text_style)
            if hasattr(self.win, 'actual_mode_label'): self.win.actual_mode_label.setStyleSheet(gray_text_style)
            if hasattr(self.win, 'measure_label'): self.win.measure_label.setStyleSheet(gray_text_style)
            if hasattr(self.win, 'measure'): self.win.measure.setStyleSheet(gray_text_style)
            if hasattr(self.win, 'mode_label'): self.win.mode_label.setStyleSheet(gray_text_style)
            if hasattr(self.win, 'label_In_Out'): self.win.label_In_Out.setStyleSheet(gray_text_style)
            if hasattr(self.win, 'inlet_valve_label'): self.win.inlet_valve_label.setStyleSheet(gray_text_style)


        else:
            if self.is_offline:
                print("Connection to device re-established...")
                self.is_offline = False

                try:
                    valve1_output = self.instrument.readParameter(55)
                    if valve1_output is not None:
                        current_valve_value = calculate_valve_percentage(valve1_output)
                        self.update_inlet_valve_display(current_valve_value)
                    else:
                        # This block runs if the read value is None
                        if hasattr(self.win, 'inlet_valve_label'):
                            self.win.inlet_valve_label.setText("...")
                except Exception as e:
                    print(f"Failed to perform valve read on reconnect: {e}")
                    if hasattr(self.win, 'inlet_valve_label'):
                        self.win.inlet_valve_label.setText("...")
            # --- ONLINE STATE: Re-enable UI elements and restore styles ---
            # --- Re-enable Controls ---
            self.win.plotButton.setEnabled(True)
            self.win.openButton.setEnabled(True)
            self.win.closeButton.setEnabled(True)
            self.win.setpoint.setEnabled(True)
            if hasattr(self.win, 'admin_button'):
                self.win.admin_button.setEnabled(True)

            # --- Restore Default Styles ---
            self.win.plotButton.setStyleSheet("")  # Revert to default stylesheet

            # Restore label colors (assuming default is white for a dark theme)
            default_label_color = "color: white;"
            if hasattr(self.win, 'setpoint_label'): self.win.setpoint_label.setStyleSheet(default_label_color)
            if hasattr(self.win, 'actual_mode_label'): self.win.actual_mode_label.setStyleSheet(default_label_color)
            if hasattr(self.win, 'measure_label'): self.win.measure_label.setStyleSheet(default_label_color)
            if hasattr(self.win, 'measure'): self.win.measure.setStyleSheet(default_label_color)
            if hasattr(self.win, 'mode_label'): self.win.mode_label.setStyleSheet(default_label_color)
            if hasattr(self.win, 'inlet_valve_label'):
                if self.valve_status == "closed":
                    self.win.inlet_valve_label.setStyleSheet("color: gray;")
                else:
                    self.win.inlet_valve_label.setStyleSheet(default_label_color)

            if hasattr(self.win, 'label_In_Out'):
                if self.valve_status == "closed":
                    self.win.label_In_Out.setStyleSheet("color: gray;")
                else:
                    self.win.label_In_Out.setStyleSheet(default_label_color)

            # --- Restore Button and Valve Status Label states ---
            if self.valve_status == "PID":
                self.win.openButton.setStyleSheet("background-color: green;")
                self.win.closeButton.setStyleSheet("background-color: gray;")
                self.win.label_valve_status.setText("PID")
                self.win.label_valve_status.setStyleSheet("color: white;")
            elif self.valve_status == "closed":
                self.win.openButton.setStyleSheet("background-color: gray;")
                self.win.closeButton.setStyleSheet("background-color: red;")
                self.win.label_valve_status.setText("Closed")

                # --- THIS IS THE FIX ---
                # Only start the timer if it isn't already running
                if not self.flicker_timer.isActive():
                    self.flicker_timer.start(500)

            # --- Update the device status text and color ---
            if status == 'error':
                self.win.device_status_label.setText('ERROR')
                self.win.device_status_label.setStyleSheet("color: red; font-weight: bold;")
            elif status == 'warning':
                self.win.device_status_label.setText('Warning')
                self.win.device_status_label.setStyleSheet("color: orange; font-weight: bold;")
            else:  # 'normal'
                self.win.device_status_label.setText('Normal')
                self.win.device_status_label.setStyleSheet("color: green;")


    def update_log(self, text):
        """Appends text to the QTextEdit."""
        cursor = self.win.log_display.textCursor()
        cursor.movePosition(cursor.End)
        cursor.insertText(text)
        self.win.log_display.setTextCursor(cursor)
        self.win.log_display.ensureCursorVisible()

    def actionButton(self):
        self.win.openButton.clicked.connect(self.valve_PID)
        self.win.closeButton.clicked.connect(self.valve_close)
        self.win.setpoint.editingFinished.connect(self.setPoint)
        if hasattr(self.win, 'plotButton'):
            self.win.plotButton.clicked.connect(self.show_plot_window)
        if hasattr(self.win, 'admin_button'):
            self.win.admin_button.clicked.connect(self.open_admin_panel)
        if hasattr(self.win, 'help_button'):
            self.win.help_button.clicked.connect(self.show_help_window)



    def open_admin_panel(self):
        # The correct password
        CORRECT_PASSWORD = "123"

        # Pop up the password dialog
        password, ok = QInputDialog.getText(self,
                                            "Admin Access",
                                            "Enter Password:",
                                            QLineEdit.Password)  # This hides the text

        # Check if the user clicked "OK" and if the password is correct
        if ok and password == CORRECT_PASSWORD:
            print("Password correct. Opening admin panel.")

            # We store the window as an attribute of the main class
            # to prevent it from being garbage collected and disappearing.
            self.admin_w = AdminWindow(self)
            self.admin_w.show()
            # Get the geometry of the main window
            main_geo = self.geometry()

            # Get the width of the admin window
            admin_width = self.admin_w.frameGeometry().width()

            # Get the top-left point of the main window
            top_left_point = main_geo.topLeft()

            # Calculate the new top-left point for the admin window and move it
            # The new X is the main window's X minus the admin window's width
            new_x = top_left_point.x() - admin_width
            new_y = top_left_point.y()
            self.admin_w.move(new_x, new_y)

            # Bring the window to the front
            self.admin_w.activateWindow()


        elif ok:  # If they clicked OK but the password was wrong
            QMessageBox.warning(self, "Access Denied", "Incorrect password.")

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



    def read_initial_setpoint(self):
        raw_setpoint = self.instrument.readParameter(9)
        #abs_setpoint = (float(raw_setpoint) / 32000.0) * 100.0
        bar_setpoint = self.propar_to_bar(raw_setpoint, self.capacity)
        self.win.setpoint.blockSignals(True)
        self.win.setpoint.setValue(bar_setpoint)
        self.win.setpoint.blockSignals(False)

        # Send the initial setpoint to the plot window
        self.plot_window.set_setpoint_value(bar_setpoint)

    def show_plot_window(self):
        """ Shows the plot window when the button is clicked. """
        self.plot_window.show()


    def valve_PID(self):
        print('Valve PID controlled')
        #stop flickering
        self.flicker_timer.stop()
        self.win.label_valve_status.setStyleSheet("color: white;")
        self.win.label_valve_status.setText('PID')
        self.win.openButton.setStyleSheet("background-color: green")
        self.win.closeButton.setStyleSheet("background-color: gray")
        self.instrument.writeParameter(12, 0)  # 'PID Control' command
        self.valve_status = "PID"
        time.sleep(0.2)
        if hasattr(self.win, 'inlet_valve_label'):
            self.win.inlet_valve_label.setStyleSheet("color: white;")
            self.win.inlet_valve_label.setText("... %")
        if hasattr(self.win, 'label_In_Out'):
            self.win.label_In_Out.setStyleSheet("color: white;")
        try:
            valve1_output = self.instrument.readParameter(55)
            if valve1_output is not None:
                current_valve_value = calculate_valve_percentage(valve1_output)
                self.update_inlet_valve_display(current_valve_value)
            else:
                # This block runs if the read value is None
                if hasattr(self.win, 'inlet_valve_label'):
                    self.win.inlet_valve_label.setText("...")
        except Exception as e:
            print(f"Failed to perform initial valve read: {e}")
            if hasattr(self.win, 'inlet_valve_label'):
                self.win.inlet_valve_label.setText("...")
        except Exception as e:
            print(f"Failed to perform initial valve read: {e}")
            if hasattr(self.win, 'inlet_valve_label'):
                self.win.inlet_valve_label.setText("... %")


    def valve_close(self):
        print('Valve closed')
        self.win.label_valve_status.setText('Closed')
        #self.win.label_valve_status.setStyleSheet("color: red; font-weight: bold;")
        self.win.closeButton.setStyleSheet("background-color: red")
        self.win.openButton.setStyleSheet("background-color: gray")
        self.flicker_timer.start(500)  # 500 ms interval
        self.instrument.writeParameter(12, 3)  # 'Valve Closed' command
        self.valve_status = "closed"
        #if hasattr(self.win, 'absolute_measure'):
        #    self.win.absolute_measure.setText("0.00")
        if hasattr(self.win, 'inlet_valve_label'):
            self.win.inlet_valve_label.setStyleSheet("color: gray;")
            self.win.inlet_valve_label.setText("...")
        if hasattr(self.win, 'label_In_Out'):
            self.win.label_In_Out.setStyleSheet("color: gray;")

    def setPoint(self):
        # Do not try to send a setpoint if the device is offline.
        if self.is_offline:
            return

        bar_setpoint = self.win.setpoint.value()
        print(f"Bar setpoint set to: {bar_setpoint} {self.unit}")
        self.plot_window.set_setpoint_value(bar_setpoint)
        if self.capacity > 0:
            # Convert absolute setpoint to a percentage
            propar_value = self.bar_to_propar(bar_setpoint, self.capacity)
            self.instrument.writeParameter(9, propar_value)

            # --- Re-engage control mode every time setpoint changes ---
            if self.valve_status == "PID":  # Only send if in PID mode
                self.instrument.writeParameter(12, 0)  # 'Setpoint Control' command
        else:
            print("Warning: Cannot set point, device capacity is unknown or zero.")



    def update_inlet_valve_display(self, raw_value):
        if self.valve_status != "closed":
            if hasattr(self.win, 'inlet_valve_label'):
                self.win.inlet_valve_label.setText(f"{raw_value:.2f}")


    def update_debug_display(self, raw_value):
        """Updates the debug display with a raw value from the thread."""
        if hasattr(self.win, 'debug_param_output'):
            self.win.debug_param_output.setText(f"{int(raw_value)} %")

    def aff(self, timestamp, M):
        # This function updates the display with the measurement from the thread

        # This part updates always, regardless of valve state, to show pressure
        if self.capacity > 0:
            absolute_value = (float(M) / 100.0) * self.capacity
            #if hasattr(self.win, 'absolute_measure'):
            #    self.win.absolute_measure.setText(f"{absolute_value:.2f}")
            s_percent = float(M)
            # Use f-string formatting to always show two decimal places
            self.win.measure.setText(f"{s_percent:.2f}")

        elif self.valve_status == "Closed":
            self.label_win.valve_status.setText('Closed')


    def closeEvent(self, event):
        # Disconnect the signal to prevent it from firing during shutdown.
        self.win.setpoint.editingFinished.disconnect(self.setPoint)
        print("Closing application...")

        if hasattr(self, 'plot_window'):
            self.plot_window.close()
        if hasattr(self, 'help_w') and self.help_w.isVisible():
            self.help_w.close()
        if hasattr(self, 'admin_w') and self.admin_w.isVisible():
            self.admin_w.close()

        if hasattr(self, 'threadFlow'):
            self.threadFlow.stopThread()

        time.sleep(0.1)
        if self.connection_successful:
            if hasattr(self, 'instrument'):
                self.instrument.writeParameter(12, 3)
                print("Closing valve...")
                self.win.label_valve_status.setText('Closed')
                time.sleep(0.5)
                self.instrument.master.propar.stop()
                print("Connection closed.")
        event.accept()

    def propar_to_bar(self, propar_value, capacity):  # Added 'capacity' argument
        """Converts a raw Propar value (0-32000) to the absolute unit (bar)."""
        if propar_value is None or capacity == 0:
            return 0.0
        return (float(propar_value) / 32000.0) * capacity

    def bar_to_propar(self, bar_value, capacity):  # Added 'capacity' argument
        """Converts an absolute unit (bar) to a raw Propar value (0-32000)."""
        if bar_value is None or capacity == 0:
            return 0
        propar_float = (bar_value / capacity) * 32000.0
        return int(max(0.0, min(32000.0, propar_float)))

    def show_help_window(self):
        """
        Creates and shows an independent help window.
        """
        if not hasattr(self, 'help_w') or not self.help_w:
            # --- FIX: Pass None as the parent to make it an independent window ---
            self.help_w = HelpWindow(version=__version__, parent=None)

        # Show the window (non-modal)
        self.help_w.show()

        # Get the geometry (size and position) of the main window
        main_geo = self.geometry()
        # Get the coordinate of the main window's top-right corner
        top_right_point = main_geo.topRight()
        # Move the help window to that point
        self.help_w.move(top_right_point)

        self.help_w.activateWindow()

    def _toggle_status_label_visibility(self):
        """ Toggles the stylesheet of the status label to make it flicker. """
        if self.label_is_visible:
            # Make text transparent (same as background)
            self.win.label_valve_status.setStyleSheet("color: transparent;")
        else:
            # --- UPDATE THIS LINE to include bold ---
            self.win.label_valve_status.setStyleSheet("color: red; font-weight: bold;")

        # Flip the state for the next tick
        self.label_is_visible = not self.label_is_visible



class THREADFlow(QtCore.QThread):
    MEAS = QtCore.pyqtSignal(float, float)
    VALVE1_MEAS = QtCore.pyqtSignal(float)
    DEBUG_MEAS = QtCore.pyqtSignal(float)
    DEVICE_STATUS_UPDATE = QtCore.pyqtSignal(str)

    def __init__(self, parent, capacity):
        super(THREADFlow, self).__init__(parent)
        self.parent = parent
        self.instrument = self.parent.instrument
        self.propar_to_bar_func = self.parent.propar_to_bar
        self.capacity = capacity
        self.stop = False

    def run(self):
        while not self.stop:
            try:
                # --- Perform all reads first ---
                alarm_status = self.instrument.readParameter(28)
                raw_measure = self.instrument.readParameter(8)
                valve1_output = self.instrument.readParameter(55)  # Read the valve output here as well

                # If a critical read like pressure fails (returns None),
                # we assume the connection is lost.
                if raw_measure is None:
                    self.DEVICE_STATUS_UPDATE.emit('offline')
                    time.sleep(1)
                    continue

                # --- If reads were successful, process the data ---
                if alarm_status is not None:
                    if alarm_status & 1:
                        self.DEVICE_STATUS_UPDATE.emit('error')
                    elif alarm_status & 2:
                        self.DEVICE_STATUS_UPDATE.emit('warning')
                    else:
                        self.DEVICE_STATUS_UPDATE.emit('normal')

                timestamp = time.monotonic()
                bar_measure = self.propar_to_bar_func(raw_measure, self.capacity)
                self.MEAS.emit(timestamp, bar_measure)

                # --- THIS IS THE CORRECTED LOGIC ---
                # STEP 2: Calculate the value and EMIT the signal
                if valve1_output is not None:
                    current_valve_value = calculate_valve_percentage(valve1_output)
                    # Emit the signal with the calculated percentage
                    self.VALVE1_MEAS.emit(current_valve_value)
                # No 'else' block is needed here, because if the read fails,
                # no signal is sent, and the display simply won't update for that cycle.

            except Exception as e:
                self.DEVICE_STATUS_UPDATE.emit('offline')
                print(f"Error reading from instrument: {e}")

            time.sleep(0.1)
        print('Measurement thread stopped.')

    def stopThread(self):
        self.stop = True


if __name__ == '__main__':
    appli = QApplication(sys.argv)
    appli.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())

    main_window = None

    while True:  # Start the selection loop
        available_ports = [port.device for port in serial.tools.list_ports.comports()]

        if not available_ports:
            QMessageBox.critical(None, "Connection Error",
                                 "No COM ports found. Please ensure your device is connected.")
            sys.exit()  # Exit if no ports are found at all

        selected_port, ok = QInputDialog.getItem(
            None, "Select COM Port", "Connect to Bronkhorst device on:",
            available_ports, 0, False
        )

        if ok and selected_port:
            print(f"Attempting to connect to {selected_port}...")
            # Create a temporary instance to check the connection
            main_window = Bronkhost(com=selected_port,name="LOA Pressure Control")

            # Check the flag we created. If it's True, the connection worked.
            if main_window.connection_successful:
                break  # Exit the loop on success
            else:
                # If connection failed, the error message from __init__ was already shown.
                # The loop will now repeat, showing the selection dialog again.
                continue
        else:
            # If the user clicks "Cancel" on the dialog
            main_window = None  # Ensure no window is shown
            break  # Exit the loop

    # The loop is finished, now we check if we have a valid window
    if main_window and main_window.connection_successful:
        print("Connection established. Starting application.")
        main_window.show()
        appli.exec_()
    else:
        print("No valid port selected. Exiting application.")
        sys.exit()

