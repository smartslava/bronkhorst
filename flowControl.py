# Force qtpy (used by qdarkstyle) to initialize with the correct binding
import qtpy

# -*- coding: utf-8 -*-
"""
Created on Wed Jun 21 15:26:36 2023
@author: SALLEJAUNE & Slava Smartsev
"""
__version__ = "1.1.0"
import pathlib, os
os.environ['QT_API'] = 'pyqt6'
from admin_window import AdminWindow
from help_window import HelpWindow
import propar
from PyQt6 import QtCore, uic
from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow, QInputDialog, QMessageBox, QLineEdit

import datetime as dt
import pyqtgraph as pg

from PyQt6.QtGui import QIcon
import sys
import time
import qdarkstyle
from PyQt6.QtCore import Qt

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
from PyQt6.QtWidgets import QDoubleSpinBox
from PyQt6.QtCore import Qt, QTimer

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


class TimeAxisItem(pg.AxisItem):
    """
    Custom AxisItem that displays system timestamps (seconds since epoch)
    converted explicitly from UTC to local time zone.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enableAutoSIPrefix(False)

    def tickStrings(self, values, scale, spacing):
        strings = []
        for value in values:
            try:
                # 1. Create a datetime object using the raw timestamp, assuming it is UTC.
                #    We use utcfromtimestamp to avoid locale ambiguities, though fromtimestamp
                #    should work if you are on a very old Python version.
                #    A simpler way for modern python is: dt.datetime.fromtimestamp(value, dt.timezone.utc)

                # --- The most robust conversion to local time ---
                utc_dt = dt.datetime.fromtimestamp(value, dt.timezone.utc)

                # 2. Convert the UTC time to the local time zone of the machine.
                local_dt = utc_dt.astimezone(None)  # None uses the system's local time zone

                # 3. Format the LOCALIZED datetime object to display time as HH:MM:SS
                strings.append(local_dt.strftime('%H:%M:%S'))

            except Exception:
                strings.append('')
        return strings

class PlotWindow(QMainWindow):
    # ... (other code)

    def __init__(self, parent=None):
        # 1. Initialize the QMainWindow superclass
        super(PlotWindow, self).__init__(parent)

        self.setWindowTitle('Real-Time Pressure Plot')

        self.graphWidget = pg.PlotWidget(axisItems={'bottom': TimeAxisItem(orientation='bottom')})
        self.setCentralWidget(self.graphWidget)

        # 3. Styling the plot
        self.graphWidget.setBackground('k')
        self.graphWidget.setTitle("Pressure Reading (bar)", color="w", size="15pt")
        styles = {'color': 'w', 'font-size': '12pt'}
        self.graphWidget.setLabel('left', 'Pressure (bar)', **styles)
        # *** FIX: Update the label from 'Time (s)' to 'Time (HH:MM:SS)' ***
        self.graphWidget.setLabel('bottom', 'Time (HH:MM:SS)', **styles)
        self.graphWidget.showGrid(x=True, y=True)
        self.graphWidget.getAxis('bottom').setPen('w')
        self.graphWidget.getAxis('left').setPen('w')

        # 4. Initialize Data Storage (MAX_HISTORY_POINTS needs to be defined near the class)
        MAX_HISTORY_POINTS = 24000 #around 1 hour
        self.time_data = deque(maxlen=MAX_HISTORY_POINTS)
        self.pressure_data = deque(maxlen=MAX_HISTORY_POINTS)
        self.setpoint_data = deque(maxlen=MAX_HISTORY_POINTS)
        #self.start_time = time.monotonic()


        self.max_duration = 10.0  # Default visible duration in seconds

        # 5. Initialize Plot Lines
        pen = pg.mkPen(color=(255, 255, 0), width=2)
        self.data_line = self.graphWidget.plot(list(self.time_data), list(self.pressure_data), pen=pen)

        setpoint_pen = pg.mkPen(color=(255, 0, 0), width=1.5)
        self.setpoint_line = self.graphWidget.plot(pen=setpoint_pen)

        # 6. Initialize Setpoint State
        self.current_setpoint = 0.0




        def tickStrings(self, values, scale, spacing):
            """
            Formats the tick values (which are seconds from self.start_time)
            into HH:MM:SS strings.
            """
            strings = []
            for value in values:
                try:
                    # Convert the float time-in-seconds to a datetime.timedelta object
                    td = dt.timedelta(seconds=value)

                    # Format the timedelta object into HH:MM:SS
                    # We need to manually handle hours greater than 23
                    total_seconds = int(td.total_seconds())
                    hours, remainder = divmod(total_seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)

                    # Format: Hours padded to 2 digits, Minutes padded to 2 digits, Seconds padded to 2 digits
                    strings.append(f'{hours:02d}:{minutes:02d}:{seconds:02d}')
                except OverflowError:
                    # Fallback for extremely large values
                    strings.append('')
            return strings

    def set_max_duration(self, duration_s: float):
        """Sets the new maximum duration (in seconds) for the plot's X-axis."""
        if duration_s > 0:
            self.max_duration = duration_s
            # When duration changes, it forces a refresh of the plotted data
            self.update_plot_viewport()

    def set_setpoint_value(self, value):
        """A simple slot to receive and store the current setpoint value."""
        self.current_setpoint = value

    def update_plot(self, timestamp, pressure_value):
        """ This method receives new data, appends it to the history, and updates the plot view. """

        # *** FIX: Remove the elapsed time calculation! ***
        # The incoming 'timestamp' from THREADFlow is now the absolute x-value (time.time())
        # The line 'elapsed_time = timestamp - self.start_time' is no longer needed.

        # 1. Append new data (using the absolute timestamp directly)
        self.time_data.append(timestamp)  # Use the absolute timestamp here
        self.pressure_data.append(pressure_value)
        self.setpoint_data.append(self.current_setpoint)

        # 2. Update the plot lines
        self.data_line.setData(list(self.time_data), list(self.pressure_data))
        self.setpoint_line.setData(list(self.time_data), list(self.setpoint_data))

        # 3. Adjust the viewport to show the desired max_duration
        self.update_plot_viewport()

    def update_plot_viewport(self):
        """Automatically adjusts the X-axis view to match the current duration setting,
        clipping the view to the actual recorded history."""

        if self.time_data:
            x_max = self.time_data[-1]

            # 1. Calculate the minimum time required by the max_duration setting
            required_x_min = x_max - self.max_duration

            # 2. Get the actual oldest time currently in the deque
            actual_x_min = self.time_data[0]

            # 3. Clip the visible minimum (x_min) to be the larger of the two values.
            #    This prevents viewing time before the first recorded point.
            x_min = max(required_x_min, actual_x_min)

            # 4. Set the X-Range of the plot
            self.graphWidget.setXRange(x_min, x_max, padding=0)

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

        # Initialize plot_window to None to prevent AttributeError if connection fails
        self.plot_window = None

        # -----Flickering Label-----------
        self.flicker_timer = QTimer(self)
        self.flicker_timer.timeout.connect(self._toggle_status_label_visibility)
        self.label_is_visible = True  # State tracker for the flicker

        # --- REDIRECT PRINT STATEMENTS ---
        self.log_stream = Stream()
        self.log_stream.new_text.connect(self.update_log)
        sys.stdout = self.log_stream
        print(f"--- LOA Pressure Control v{__version__} ---")

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

        # -------------------------------------------------------------------
        # *** START SUCCESSFUL CONNECTION BLOCK ***
        # -------------------------------------------------------------------
        self.setWindowTitle(f"{name} v{__version__}")
        self.icon = str(p.parent) + sepa + 'icons' + sepa
        self.setWindowIcon(QIcon(self.icon + 'LOA3.png'))
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.raise_()

        # Set valve to closed on startup
        self.valve_close()

        # --- Read device capacity and units ---
        self.capacity = 0.0
        self.unit = ""
        self.read_device_info()

        # 1. Initialize PlotWindow
        self.plot_window = PlotWindow(self)

        # 2. Setup UI connections
        self.actionButton()

        # 3. Read initial setpoint
        self.read_initial_setpoint()

        # 4. Initialize and start the thread
        self.threadFlow = THREADFlow(self, capacity=self.capacity)
        self.threadFlow.start()

        # 5. Connect thread signals
        self.threadFlow.MEAS.connect(self.aff)
        self.threadFlow.VALVE1_MEAS.connect(self.update_inlet_valve_display)
        self.threadFlow.DEBUG_MEAS.connect(self.update_debug_display)
        self.threadFlow.MEAS.connect(self.plot_window.update_plot)
        self.threadFlow.DEVICE_STATUS_UPDATE.connect(self.update_device_status)

        self.win.title_2.setText('Pressure Control')

    def update_device_status(self, status: str):
        """Updates the device status label and enables/disables controls."""
        # Track previous status to avoid repeated reads
        if not hasattr(self, '_last_status'):
            self._last_status = None

        # Update the UI label
        if hasattr(self.win, 'device_status_label'):
            self.win.device_status_label.setText(status)

        normalized_status = status.lower().strip()

        # --- OFFLINE STATE ---
        if normalized_status == 'offline':
            if not self.is_offline:
                print("Connection to device lost...")
                self.is_offline = True

            self.win.device_status_label.setText('Offline')
            self.win.device_status_label.setStyleSheet("color: red;")

            # Stop flickering, disable UI, gray out everything
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

            self.win.openButton.setStyleSheet("background-color: gray;")
            self.win.closeButton.setStyleSheet("background-color: gray;")
            self.win.plotButton.setStyleSheet("background-color: gray;")

            gray_text_style = "color: gray;"
            for attr in [
                'setpoint_label', 'actual_mode_label', 'measure_label', 'measure',
                'mode_label', 'label_In_Out', 'inlet_valve_label', 'user_tag_label'
            ]:
                if hasattr(self.win, attr):
                    getattr(self.win, attr).setStyleSheet(gray_text_style)

        # --- NORMAL STATE ---
        elif normalized_status == "normal":
            # *** FIX: Reset the offline flag immediately ***
            if self.is_offline:
                self.is_offline = False
                print("Device back online. Resetting offline status.")

            # Only trigger the refresh once per transition
            if self._last_status != "normal":
                print("Device status back to Normal — refreshing device info...")

                # Resynchronize Setpoint only if plot_window is initialized
                if self.plot_window is not None:
                    self._resync_setpoint()

                self.read_device_info()

                try:
                    valve1_output = self.instrument.readParameter(55)
                    if valve1_output is not None:
                        current_valve_value = calculate_valve_percentage(valve1_output)
                        self.update_inlet_valve_display(current_valve_value)
                    else:
                        if hasattr(self.win, 'inlet_valve_label'):
                            self.win.inlet_valve_label.setText("...")
                except Exception as e:
                    print(f"Failed to perform valve read on reconnect: {e}")
                    if hasattr(self.win, 'inlet_valve_label'):
                        self.win.inlet_valve_label.setText("...")

                # Re-enable UI
                self.win.plotButton.setEnabled(True)
                self.win.openButton.setEnabled(True)
                self.win.closeButton.setEnabled(True)
                self.win.setpoint.setEnabled(True)
                if hasattr(self.win, 'admin_button'):
                    self.win.admin_button.setEnabled(True)

                # Restore colors
                default_label_color = "color: white;"
                for attr in [
                    'setpoint_label', 'actual_mode_label', 'measure_label', 'measure',
                    'mode_label', 'user_tag_label', 'inlet_valve_label', 'label_In_Out'
                ]:
                    if hasattr(self.win, attr):
                        getattr(self.win, attr).setStyleSheet(default_label_color)

                # Restore buttons and valve labels
                if self.valve_status == "PID":
                    self.win.openButton.setStyleSheet("background-color: green;")
                    self.win.closeButton.setStyleSheet("background-color: gray;")
                    self.win.label_valve_status.setText("PID")
                    self.win.label_valve_status.setStyleSheet("color: white;")
                elif self.valve_status == "closed":
                    self.win.openButton.setStyleSheet("background-color: gray;")
                    self.win.closeButton.setStyleSheet("background-color: red;")
                    self.win.label_valve_status.setText("Closed")
                    if not self.flicker_timer.isActive():
                        self.flicker_timer.start(500)

                # Update status text and color
                self.win.device_status_label.setText('Normal')
                self.win.device_status_label.setStyleSheet("color: green;")

        # --- ERROR or WARNING STATE ---
        elif normalized_status == 'error':
            self.win.device_status_label.setText('ERROR')
            self.win.device_status_label.setStyleSheet("color: red;")
        elif normalized_status == 'warning':
            self.win.device_status_label.setText('Warning')
            self.win.device_status_label.setStyleSheet("color: orange;")

        # Update last status for transition detection
        self._last_status = normalized_status

    def _resync_setpoint(self):
        """
        Forces the current value in the QDoubleSpinBox to be written
        to the instrument, bypassing any signal-based issues after reconnection.
        """
        # 1. Temporarily disconnect the signal to prevent re-triggering itself
        # This is a safer alternative to blockSignals(True) for complex interactions.
        try:
            self.win.setpoint.editingFinished.disconnect(self.setPoint)
        except TypeError:
            # Handle case where it might already be disconnected (safe)
            pass

        # 2. Execute the actual setpoint logic
        self.setPoint()

        # 3. Reconnect the signal
        self.win.setpoint.editingFinished.connect(self.setPoint)

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

        # Safely connect the plot duration spinbox
        if self.plot_window is not None and hasattr(self.win, 'plot_duration_spinbox'):
            # Set the initial value (as an integer)
            integer_duration = int(self.plot_window.max_duration)
            self.win.plot_duration_spinbox.setValue(integer_duration)
            self.win.plot_duration_spinbox.editingFinished.connect(self._setPlotDuration)

    def update_user_tag_label(self, tag_string: str):
        if not hasattr(self.win, 'user_tag_label'):
            return
        try:
            display_text = str(tag_string).strip() or "—"
            self.win.user_tag_label.setText(display_text)
        except Exception as e:
            print(f"Failed to update user tag label: {e}")

    def _setPlotDuration(self):
        """
        Reads the integer value from the spinbox and updates the plot duration
        in the plot window, triggered when editing is finished.
        """
        if self.is_offline or self.plot_window is None:
            return

        # Read the integer value from the spin box
        new_duration_int = self.win.plot_duration_spinbox.value()

        print(f"Plot duration set to: {new_duration_int} seconds (applied on finish)")

        # Pass the value (as float) to the PlotWindow method
        self.plot_window.set_max_duration(float(new_duration_int))

    def open_admin_panel(self):
        # The correct password
        CORRECT_PASSWORD = "appli"

        # Pop up the password dialog
        password, ok = QInputDialog.getText(self,
                                            "Admin Access",
                                            "Enter Password:",
                                            QLineEdit.EchoMode.Password)  # This hides the text

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
            user_tag_raw = self.instrument.readParameter(115)

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
                    self.win.unit_label.setStyleSheet("font-size: 16pt; color: white;")
            else:
                print("Warning: Could not read device unit (param 129).")

            if user_tag_raw is not None:
                if isinstance(user_tag_raw, (bytes, bytearray)):
                    try:
                        user_tag = user_tag_raw.decode('utf-8', errors='ignore')
                    except Exception:
                        user_tag = str(user_tag_raw)
                else:
                    user_tag = str(user_tag_raw)
                self.update_user_tag_label(user_tag)

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
        # *** FIX 2: Guard against running while offline ***
        if self.is_offline or not self.connection_successful:
            print("Set point skipped: Device is offline.")
            return

        bar_setpoint = self.win.setpoint.value()
        print(f"Bar setpoint set to: {bar_setpoint} {self.unit}")
        self.plot_window.set_setpoint_value(bar_setpoint)

        if self.capacity > 0:
            propar_value = self.bar_to_propar(bar_setpoint, self.capacity)
            self.instrument.writeParameter(9, propar_value)

            # --- Re-engage control mode every time setpoint changes ---
            # *** FIX 3: Ensure the PID command is sent to activate the new setpoint ***
            if self.valve_status == "PID":
                self.instrument.writeParameter(12, 0)  # 'PID Control' command
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
            self.win.label_valve_status.setStyleSheet("color: red;")

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
                        self.DEVICE_STATUS_UPDATE.emit('Error')
                    elif alarm_status & 2:
                        self.DEVICE_STATUS_UPDATE.emit('Warning')
                    else:
                        self.DEVICE_STATUS_UPDATE.emit('Normal')

                #timestamp = time.monotonic()
                timestamp = time.time()
                bar_measure = self.propar_to_bar_func(raw_measure, self.capacity)
                self.MEAS.emit(timestamp, bar_measure)

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

            time.sleep(0.15)
        print('Measurement thread stopped.')

    def stopThread(self):
        self.stop = True


if __name__ == '__main__':
    appli = QApplication(sys.argv)
    appli.setStyleSheet(qdarkstyle.load_stylesheet())
    #appli.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())

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

