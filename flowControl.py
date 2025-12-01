# Force qtpy (used by qdarkstyle) to initialize with the correct binding
import qtpy

# -*- coding: utf-8 -*-
"""
Created on Wed Jun 21 15:26:36 2023
@author: SALLEJAUNE & Slava Smartsev
"""
__version__ = "1.2.1-beta"
import pathlib, os
os.environ['QT_API'] = 'pyqt6'
from admin_window import AdminWindow
from help_window import HelpWindow
import propar
from PyQt6 import QtCore, uic
from PyQt6.QtWidgets import (QApplication, QWidget, QMainWindow, QInputDialog, QMessageBox, QLineEdit, QButtonGroup)

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
import configparser


def load_configuration():
    config = configparser.ConfigParser()
    # This gets the directory of the current python script file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'config.ini')

    # Default values in case file is missing
    defaults = {
        'Connection': {'default_com_port': 'COM1'},
        'Safety': {
            'max_set_pressure': '100.0',
            'set_point_above_tolerance': '1',
            'set_point_above_delay': '2',
            'set_point_above_safety_enable': '1',
            'purge_shut_delay': '2'
            # ----------------------
        },
        'Thread': {'thread_sleep_time': '0.2'},
        'Plotting': {
            'max_history': '24000',
            'default_duration': '10',

        },
        'Security': {'admin_password': 'appli'},
        'UI': {'window_title': 'LOA Pressure Control'}
    }

    # Load the file
    # Read from the absolute path
    if os.path.exists(config_path):
        print(f"Loading config from: {config_path}")  # Debug print
        config.read(config_path)
    else:
        print(f"Config not found at {config_path}, creating defaults.")
        config.read_dict(defaults)
        with open(config_path, 'w') as f:
            config.write(f)

    return config


# Load config globally or pass it down
#APP_CONFIG = load_configuration()



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

    def __init__(self, parent=None, max_history=24000, default_duration=10.0,
                 p_color='#FFFF00', s_color='#FF0000',user_tag=""):
        # 1. Initialize the QMainWindow superclass
        super(PlotWindow, self).__init__(parent)
        self.resize(400, 300)  # Width, Height in pixels
        self.max_duration = float(default_duration)
        self.setWindowTitle('Real-Time Pressure Plot')

        self.graphWidget = pg.PlotWidget(axisItems={'bottom': TimeAxisItem(orientation='bottom')})
        self.setCentralWidget(self.graphWidget)

        self.graphWidget.getViewBox().enableAutoRange(axis='y', enable=True)
        self.graphWidget.getViewBox().setAutoVisible(y=True)

        # 3. Styling the plot
        self.graphWidget.setBackground('k')
        self.update_title(user_tag)
        gray_color = '#C0C0C0'
        styles = {'color': gray_color, 'font-size': '10pt'}
        self.graphWidget.setLabel('left', 'Pressure (bar)', **styles)
        # *** FIX: Update the label from 'Time (s)' to 'Time (HH:MM:SS)' ***
        self.graphWidget.setLabel('bottom', 'Local Time', **styles)

        self.graphWidget.showGrid(x=True, y=True, alpha=0.2)
        self.graphWidget.getAxis('bottom').setPen(gray_color)
        self.graphWidget.getAxis('left').setPen(gray_color)

        # 4. Initialize Data Storage (MAX_HISTORY_POINTS needs to be defined near the class)
        #MAX_HISTORY_POINTS = 24000 #around 1 hour
        self.time_data = deque(maxlen=int(max_history))
        self.pressure_data = deque(maxlen=int(max_history))
        self.setpoint_data = deque(maxlen=int(max_history))
        #self.start_time = time.monotonic()


        #self.max_duration = 10.0  # Default visible duration in seconds

        # 5. Initialize Plot Lines
        pen = pg.mkPen(color=p_color, width=2)
        self.data_line = self.graphWidget.plot(list(self.time_data), list(self.pressure_data), pen=pen)

        # --- Setpoint Line ---
        setpoint_pen = pg.mkPen(color=s_color, width=1.5)  # slightly thinner
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

    def update_title(self, user_tag=""):
        """Updates the plot title to include the User Tag if available."""
        base_title = "Pressure Reading and Setpoint"
        if user_tag and user_tag != "—":
            full_title = f"{base_title} - {user_tag}"
        else:
            full_title = base_title

        self.graphWidget.setTitle(full_title, color="#C0C0C0", size="12pt")
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

    def __init__(self, com=None, config=None, parent=None):
        if com is None:
            # If no port was given, maybe pop up the selection dialog right here!
            # Or print an error, etc.
            print("Error: No COM port was provided.")
            return  # Stop initialization

        self.config = config  # Store config for later use

        super(Bronkhost, self).__init__(parent)
        self.is_offline = False
        self.connection_successful = False
        p = pathlib.Path(__file__)
        sepa = os.sep
        self.win = uic.loadUi('flow.ui', self)

        # --- GROUPING RADIO BUTTONS ---
        # This ensures they are mutually exclusive and easier to manage
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.win.radioPID)
        self.mode_group.addButton(self.win.radioShut)

        # Set ID for easier logic later (1=PID, 0=Shut)
        self.mode_group.setId(self.win.radioPID, 1)
        self.mode_group.setId(self.win.radioShut, 0)

        self.win.setpoint.setGroupSeparatorShown(False)


        self.win.setpoint.setGroupSeparatorShown(False)

        # Initialize plot_window to None to prevent AttributeError if connection fails
        self.plot_window = None

        # -----Flickering Label-----------
        self.flicker_timer = QTimer(self)
        self.flicker_timer.timeout.connect(self._toggle_status_label_visibility)
        self.label_is_visible = True  # State tracker for the flicker

        # --- Alarm Cooldown Timer ---
        self.rearm_timer = QTimer(self)
        self.rearm_timer.setSingleShot(True)
        self.rearm_timer.timeout.connect(self._reenable_alarm)
        self.last_known_setpoint = 0.0  # Track previous setpoint
        self.lower_setpoint_cooldown = 2.0  # Default value, updated later from config
        self.was_last_change_decrease = False

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
        title = self.config['UI'].get('window_title', 'LOA Pressure Control')
        self.setWindowTitle(f"{title} v{__version__}")
        #self.setWindowTitle(f"{name} v{__version__}")
        self.icon = str(p.parent) + sepa + 'icons' + sepa
        self.setWindowIcon(QIcon(self.icon + 'LOA3.png'))
        #self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.raise_()

        # Set valve to closed on startup
        self.valve_close()

        self.alarm_popup_active = False
        self.last_reset_time = 0.0

        # --- Read device capacity and units ---
        self.capacity = 0.0
        self.unit = ""
        self.response_alarm_enabled = False
        self.read_device_info()
        self.configure_response_alarm()

        # 1. Initialize PlotWindow
        #self.plot_window = PlotWindow(self)
        hist = self.config['Plotting'].getint('max_history', 24000)
        dur = self.config['Plotting'].getfloat('default_duration', 10.0)
        self.plot_window = PlotWindow(self, max_history=hist, default_duration=dur)

        # 2. Setup UI connections
        self.actionButton()

        # 3. Read initial setpoint
        self.read_initial_setpoint()

        # 4. Initialize and start the thread
        try:
            thread_time = self.config['Thread'].getfloat('thread_sleep_time', 0.2)
        except KeyError:
            # Fallback if [Thread] section is missing entirely in the file
            thread_time = 0.2
            print("Warning: [Thread] section missing in config, using default 0.2 s")

        print(f"Refresh thread_time loaded: {thread_time}")
        max_possible_seconds = hist * thread_time
        print(f"Buffer Capacity: {max_possible_seconds:.1f} seconds")

        # 3. Initialize PlotWindow
        # We read the default duration, but we cap it immediately to be safe
        config_duration = self.config['Plotting'].getfloat('default_duration', 10.0)

        # If config asks for 1000s but we only have 500s of memory, cap it.
        startup_duration = min(config_duration, max_possible_seconds)

        #self.plot_window = PlotWindow(self, max_history=hist, default_duration=startup_duration)
        col_pressure = self.config['Plotting'].get('pressure_color', '#FFFF00').strip('"\'')
        col_setpoint = self.config['Plotting'].get('setpoint_color', '#FF0000').strip('"\'')

        # 2. Initialize PlotWindow with ALL arguments
        # We pass max_history, default_duration, AND the two colors
        self.plot_window = PlotWindow(
            self,
            max_history=hist,
            default_duration=startup_duration,
            p_color=col_pressure,
            s_color=col_setpoint
        )

        # 4. CONFIGURE THE SPINBOX
        if hasattr(self.win, 'plot_duration_spinbox'):
            # Set the hard limit so user cannot click arrow up past this point
            self.win.plot_duration_spinbox.setMaximum(int(max_possible_seconds))

            # Update the displayed value to match what we actually sent to PlotWindow
            self.win.plot_duration_spinbox.setValue(int(startup_duration))

            # Add a tooltip so the user knows why it stops there
            self.win.plot_duration_spinbox.setToolTip(
                f"Max history is {int(max_possible_seconds)}s. "
                f"Limited by buffer size ({hist} points) "
                f"and thread time ({thread_time}s)."
            )

        self.threadFlow = THREADFlow(self, capacity=self.capacity, thread_sleep_time=thread_time)
        #self.threadFlow = THREADFlow(self, capacity=self.capacity)
        self.threadFlow.start()

        # 5. Connect thread signals
        self.threadFlow.MEAS.connect(self.aff)
        self.threadFlow.VALVE1_MEAS.connect(self.update_inlet_valve_display)
        self.threadFlow.DEBUG_MEAS.connect(self.update_debug_display)
        self.threadFlow.MEAS.connect(self.plot_window.update_plot)
        self.threadFlow.DEVICE_STATUS_UPDATE.connect(self.update_device_status)
        self.threadFlow.CRITICAL_ALARM.connect(self.handle_critical_alarm)

        self.win.title_2.setText('Pressure Control')

    def reset_alarm_cmd(self):
        """Sends the sequence to reset the instrument alarm."""
        try:
            print("Sending Alarm Reset Command...")
            # Good practice: Send 0 first to clear previous commands
            self.instrument.writeParameter(114, 0)
            time.sleep(0.1)
            # Send 2 to reset the alarm
            self.instrument.writeParameter(114, 2)
            time.sleep(0.1)
            # Send 0 again to finish
            self.instrument.writeParameter(114, 0)
            print("Alarm Reset Sent.")
        except Exception as e:
            print(f"Failed to reset alarm: {e}")

    def handle_critical_alarm(self, alarm_code):
        """
        Handles the CRITICAL_ALARM signal.
        AUTOMATIC SAFETY SEQUENCE:
        1. Immediate Visual Update.
        2. Immediate Reset & Hardware Sync.
        3. Schedule Shutdown Timer.
        4. Notify user (Non-blocking logic, Blocking UI).
        """
        # 1. Cooldown Check (Prevent spamming)
        if self.alarm_popup_active:
            return

        delay_setting = self.config['Safety'].getfloat('set_point_above_delay', 2.0)
        cooldown_period = delay_setting + 1.0
        if (time.time() - self.last_reset_time) < cooldown_period:
            return

        self.alarm_popup_active = True
        print(f"CRITICAL ALARM {alarm_code}: Executing AUTO-SAFETY sequence.")

        # ----------------------------------------------------------
        # STEP 1: IMMEDIATE ACTIONS (Do not wait for user)
        # ----------------------------------------------------------

        # A. Visual Update
        safe_bar = self.get_safe_setpoint_bar()
        if self.plot_window is not None:
            self.plot_window.set_setpoint_value(safe_bar)
        self.win.setpoint.blockSignals(True)
        self.win.setpoint.setValue(safe_bar)
        self.win.setpoint.blockSignals(False)

        # B. Reset Alarm Bit
        self.reset_alarm_cmd()

        # C. Sync Hardware Setpoint (Hold Safe Pressure)
        if self.capacity > 0:
            safe_propar = self.bar_to_propar(safe_bar, self.capacity)
            try:
                self.instrument.writeParameter(9, safe_propar)
                print(f"System Holding at Safe State: {safe_bar} bar")
            except Exception as e:
                print(f"Warning: Hardware sync failed: {e}")

        # D. Schedule Shutdown
        shut_delay = self.config['Safety'].getfloat('purge_shut_delay', 1.0)
        print(f"Auto-Shutdown scheduled in {shut_delay} seconds...")

        # The timer runs in the background event loop.
        # It will fire even if the popup below is still open.
        QTimer.singleShot(int(shut_delay * 1000), self._finalize_purge)

        # E. Update Cooldown Tracker
        self.last_reset_time = time.time()

        # ----------------------------------------------------------
        # STEP 2: NOTIFY USER
        # ----------------------------------------------------------
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("SAFETY SHUTDOWN")
        msg.setText("<b>Pressure Deviation Above Setpoint Detected</b>")
        msg.setInformativeText(
            f"The system has initiated an automatic safety shutdown.\n\n"
            f"1. Purging at {safe_bar} bar for {shut_delay} seconds.\n"
            f"2. Closing valve automatically.\n\n"
            f"Try to reduce PID regulation speed.\n\n"
            f"Diagnostic Code: {alarm_code}"
        )
        msg.addButton("OK", QMessageBox.ButtonRole.AcceptRole)

        # This blocks the User Interface (mouse clicks) so they must acknowledge,
        # BUT the QTimer for shutdown continues running in the background.
        msg.exec()

        self.alarm_popup_active = False

    def get_safe_setpoint_bar(self):
        """
        Single source of truth for the safe state pressure.
        Now hardcoded to 0.0 bar.
        """
        return 0.0

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
            self.win.device_status_label.setText("Offline")

            self.win.device_status_label.setStyleSheet("color: red")

            # DISABLE RADIO BUTTONS
            self.win.radioPID.setEnabled(False)
            self.win.radioShut.setEnabled(False)

            # Stop flickering, disable UI, gray out everything
            self.flicker_timer.stop()
            self.win.label_valve_status.setText("...")
            self.win.label_valve_status.setStyleSheet("color: gray;")

            self.win.measure.setText("...")
            self.win.inlet_valve_label.setText("...")

            self.win.plotButton.setEnabled(False)
            self.win.setpoint.setEnabled(False)
            self.win.plot_duration_spinbox.setEnabled(False)
            self.win.purgeButton.setEnabled(False)
            self.win.admin_button.setEnabled(False)
            self.win.plotButton.setEnabled(False)



            gray_text_style = "color: gray;"
            for attr in [
                'history_label','setpoint_label', 'actual_mode_label', 'measure_label', 'measure',
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
                self.configure_response_alarm()

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
                self.win.plot_duration_spinbox.setEnabled(True)
                self.win.radioPID.setEnabled(True)
                self.win.purgeButton.setEnabled(True)
                self.win.radioShut.setEnabled(True)
                # Restore correct selection visually based on internal state
                if self.valve_status == "PID":
                    self.win.radioPID.setChecked(True)  # Check PID
                    self.win.label_valve_status.setText("PID")
                elif self.valve_status == "closed":
                    self.win.radioShut.setChecked(True)  # Check Shut
                    self.win.label_valve_status.setText("Shut")
                    if not self.flicker_timer.isActive():
                        self.flicker_timer.start(500)
                self.win.setpoint.setEnabled(True)
                if hasattr(self.win, 'admin_button'):
                    self.win.admin_button.setEnabled(True)

                # Restore colors
                default_label_color = "color: white;"
                for attr in [
                    'history_label','setpoint_label', 'actual_mode_label', 'measure_label', 'measure',
                    'mode_label', 'user_tag_label', 'inlet_valve_label', 'label_In_Out'
                ]:
                    if hasattr(self.win, attr):
                        getattr(self.win, attr).setStyleSheet(default_label_color)

                # Restore buttons and valve labels
                if self.valve_status == "PID":
                    #self.win.openButton.setStyleSheet("background-color: green;")
                    #self.win.closeButton.setStyleSheet("background-color: gray;")
                    self.win.label_valve_status.setText("PID")
                    self.win.label_valve_status.setStyleSheet("color: white;")
                elif self.valve_status == "closed":
                    #self.win.openButton.setStyleSheet("background-color: gray;")
                    #self.win.closeButton.setStyleSheet("background-color: red;")
                    self.win.label_valve_status.setText("Shut")
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
        self.mode_group.buttonClicked.connect(self.on_mode_changed)

        self.win.setpoint.editingFinished.connect(self.setPoint)
        self.win.purgeButton.clicked.connect(self.purge_system)
        self.win.plotButton.clicked.connect(self.show_plot_window)
        self.win.admin_button.clicked.connect(self.open_admin_panel)
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
        #CORRECT_PASSWORD = "appli"
        CORRECT_PASSWORD = self.config['Security'].get('admin_password', 'appli')

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

                # Default to a high number (or self.capacity) if missing in config
                safety_limit = self.config['Safety'].getfloat('max_set_pressure', self.capacity)

                # Determine the effective maximum:
                # It is the LOWER of the physical device limit and the config safety limit
                effective_max = min(self.capacity, safety_limit)

                print(f"Safety Limit: {safety_limit} | Effective UI Max: {effective_max}")
                # --- Configure the setpoint box's range and precision ---
                if hasattr(self.win, 'setpoint'):
                    self.win.setpoint.setMaximum(effective_max)
                    self.win.setpoint.setDecimals(2)
                    self.win.setpoint.setToolTip(f"Config limited to {effective_max} (Physical: {self.capacity})")
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
            if user_tag_raw is not None:
                if isinstance(user_tag_raw, (bytes, bytearray)):
                    try:
                        user_tag = user_tag_raw.decode('utf-8', errors='ignore')
                    except Exception:
                        user_tag = str(user_tag_raw)
                else:
                    user_tag = str(user_tag_raw)

                # 1. Update the Main Window Label (Existing code)
                self.update_user_tag_label(user_tag)

                # 2. NEW: Update the Plot Window Title
                if self.plot_window is not None:
                    self.plot_window.update_title(user_tag)
        except Exception as e:
            print(f"Error reading device info: {e}")

    def configure_response_alarm(self):
        """
        Configures the Deviation Alarm.
        TOLERANCE is now defined in BARS.
        """
        if self.is_offline:
            return

        # --- 1. PAUSE THE THREAD (Thread Safety) ---
        # We stop the reading thread so it doesn't try to use the COM port
        # while we are writing complex configuration data.
        thread_was_running = False
        if hasattr(self, 'threadFlow') and self.threadFlow.isRunning():
            print("Pausing measurement thread for config...")
            self.threadFlow.stop = True
            thread_was_running = True
            # Wait up to 1000ms for the thread to actually finish
            self.threadFlow.wait(1000)


        try:
            print("--- Loading Config of Response Alarm ---")

            # 1. Read the Enable Flag
            enable_flag = self.config['Safety'].getboolean('set_point_above_safety_enable', True)
            self.response_alarm_enabled = enable_flag
            safe_pressure_bar = self.get_safe_setpoint_bar()
            # 2. Read Configuration Values
            tol_bar = self.config['Safety'].getfloat('set_point_above_tolerance', 2.0)
            print(f"Pressure tolerance: {tol_bar} bars")
            delay_sec = self.config['Safety'].getint('set_point_above_delay', 2)
            print(f"Alarm activation delay: {delay_sec} s")
            # --- Read Cooldown Delay  ---
            self.lower_setpoint_cooldown = self.config['Safety'].getfloat('set_point_lower_cooldown_delay', 2.0)
            print(f"Lower Setpoint Cooldown: {self.lower_setpoint_cooldown} s")
            print("------")

            # 3. Calculate Device Integers (0-32000)

            # --- Convert Tolerance Bar to Integer ---
            # This scales the bar value against the device capacity.
            # Example: 5 bar on 100 bar device -> (5/100)*32000 = 1600
            dev_above_int = self.bar_to_propar(tol_bar, self.capacity)
            # -------------------------------------------------------

            # Deviation Below (Min Limit) - Set to max to ignore
            dev_below_int = 32000

            # Safe Setpoint Integer
            safe_setpoint_int = self.bar_to_propar(safe_pressure_bar, self.capacity)

            print(f"Response Alarm Enable = {self.response_alarm_enabled}")
            print(f"Tolerance: {tol_bar} bar (Int: {dev_above_int})")
            print(f"Safe State: {safe_pressure_bar} bar (Int: {safe_setpoint_int})")

            # 4. Send Configuration
            self.instrument.writeParameter(118, 0)  # Disable temporarily
            self.instrument.writeParameter(116, dev_above_int)
            self.instrument.writeParameter(117, dev_below_int)
            self.instrument.writeParameter(121, safe_setpoint_int)
            self.instrument.writeParameter(120, 1)  # Enable Setpoint Change
            self.instrument.writeParameter(182, delay_sec)

            # Mode 2 is enabled dynamically in valve_PID()

        except Exception as e:
            print(f"Error configuring alarms: {e}")
        finally:
            # ---  RESTART THE THREAD ---
            # We only restart it if it was running before we paused it.
            if thread_was_running and hasattr(self, 'threadFlow'):
                print("Resuming measurement thread...")
                self.threadFlow.stop = False  # Reset the flag so the loop runs
                self.threadFlow.start()  # Restart the QThread

    def read_initial_setpoint(self):
        raw_setpoint = self.instrument.readParameter(9)
        bar_setpoint = self.propar_to_bar(raw_setpoint, self.capacity)
        self.last_known_setpoint = bar_setpoint
        self.win.setpoint.blockSignals(True)
        self.win.setpoint.setValue(bar_setpoint)
        self.win.setpoint.blockSignals(False)

        # Send the initial setpoint to the plot window
        self.plot_window.set_setpoint_value(bar_setpoint)

    def show_plot_window(self):
        """
        Shows the plot window and positions it to the top-right
        of the main window (similar to the Help window).
        """
        if self.plot_window is None:
            return

        # 1. Un-minimize and make visible first
        self.plot_window.showNormal()

        # 2. Calculate Position (Top-Right of Main Window)
        main_geo = self.geometry()
        top_right_point = main_geo.topRight()

        # 3. Move the plot window to that coordinate
        self.plot_window.move(top_right_point)

        # 4. Bring window to front and give focus
        self.plot_window.raise_()
        self.plot_window.activateWindow()

    def on_mode_changed(self, button):
        """Central handler for radio button clicks"""
        if button == self.win.radioPID:
            self.valve_PID()
        elif button == self.win.radioShut:
            self.valve_close()

    def purge_system(self):
        """
        Purge Sequence:
        1. Set Setpoint to configured purge pressure.
        2. Switch to PID mode.
        3. Wait (non-blocking) for configured delay.
        4. Switch to Shut/Closed mode.
        """
        if self.is_offline or not self.connection_successful:
            print("Purge skipped: Device is offline.")
            return

        # 1. Read Config
        try:
            #purge_sp = self.config['Safety'].getfloat('purge_set_point', 0.0)
            purge_sp = 0.0  # Static definition (hardcoded)
            delay_sec = self.config['Safety'].getfloat('purge_shut_delay', 1.0)
        except ValueError:
            print("Config Error: Invalid purge settings. Using defaults (0.0 bar, 1s).")
            purge_sp = 0.0
            delay_sec = 1.0

        print(f"--- Purge Sequence Initiated: Target={purge_sp} bar, Wait={delay_sec}s ---")

        # 2. Update UI and Send Setpoint
        # The spinbox automatically clamps the value if it exceeds device max
        self.win.setpoint.setValue(purge_sp)

        # Explicitly call setPoint to send Param 9 to the device
        self.setPoint()

        # 3. Activate PID Mode
        self.valve_PID(force_cooldown=True)
        #self.valve_PID()

        # 4. Schedule the Shutdown (Non-blocking)
        # We use QTimer.singleShot to trigger the close function after X milliseconds.
        # This keeps the GUI responsive (plotting continues) during the wait.
        print(f"Purging is active. Closing in {delay_sec} seconds...")
        QTimer.singleShot(int(delay_sec * 1000), self._finalize_purge)

    def _finalize_purge(self):
        """
        Callback function triggered by the QTimer after the purge delay.
        Closes the valve and updates the UI.
        """
        print("Purge: Delay finished. Closing valves.")

        # Close the valve
        self.valve_close()

        # Ensure the UI Radio Button reflects the change
        self.win.radioShut.setChecked(True)

    def _trigger_alarm_cooldown(self):
        """
        Disables the alarm temporarily and starts the re-arm timer.
        Used when lowering setpoint OR when switching to PID mode.
        """
        if self.response_alarm_enabled:
            try:
                print(f"Safety Wait Period: Disabling alarm for {self.lower_setpoint_cooldown}s...")

                # 1. Disable Alarm (Mode 0) immediately
                self.instrument.writeParameter(118, 0)

                # 2. Start/Restart the timer (converts seconds to ms)
                # When this timer finishes, it calls _reenable_alarm automatically
                self.rearm_timer.start(int(self.lower_setpoint_cooldown * 1000))

            except Exception as e:
                print(f"Error triggering alarm cooldown: {e}")

    def _handle_setpoint_safety_logic(self, new_bar_setpoint):
        """
        Checks if the setpoint is being lowered and updates the direction flag.
        """
        # 1. Determine direction (Always track this, even if alarms are off)
        if new_bar_setpoint < self.last_known_setpoint:
            self.was_last_change_decrease = True
            print(f"Setpoint lowered (Old:{self.last_known_setpoint} -> New:{new_bar_setpoint})")

            # If we are ALREADY in PID, try to trigger cooldown
            if self.valve_status == "PID":
                # This function checks 'if self.response_alarm_enabled' internally
                self._trigger_alarm_cooldown()

        elif new_bar_setpoint > self.last_known_setpoint:
            self.was_last_change_decrease = False
            # No immediate action needed for increase

        # 2. Always update the tracker
        self.last_known_setpoint = new_bar_setpoint

    def valve_PID(self,force_cooldown=False):
        print('Valve PID controlled')

        # 1. Update UI Visuals
        self.flicker_timer.stop()
        self.win.label_valve_status.setStyleSheet("color: white;")
        self.win.label_valve_status.setText('PID')

        # Ensure the radio button matches the logic
        self.win.radioPID.setChecked(True)

        # Reset labels to "Waiting" state
        if hasattr(self.win, 'inlet_valve_label'):
            self.win.inlet_valve_label.setStyleSheet("color: white;")
            self.win.inlet_valve_label.setText("... %")
        if hasattr(self.win, 'label_In_Out'):
            self.win.label_In_Out.setStyleSheet("color: white;")

        # 2. Send Command to Device
        self.instrument.writeParameter(12, 0)  # 'PID Control' command
        self.valve_status = "PID"

        # --- Enable Alarm if Configured ---
        if self.response_alarm_enabled:
            # Check if we lowered setpoint OR if cooldown is forced (e.g. by Purge)
            if self.was_last_change_decrease or force_cooldown:
                print("Entering PID (Setpoint drop or Purge): Triggering Cooldown.")
                self._trigger_alarm_cooldown()
            else:
                # Standard behavior: Enable alarm immediately
                try:
                    self.instrument.writeParameter(118, 2)
                    print("Safety alarm: ENABLED (Mode 2) - Immediate")
                except Exception as e:
                    print(f"Failed to enable alarm: {e}")
        # ---------------------------------------

        # 3. Attempt to read the new valve value
        time.sleep(0.1)
        try:
            valve1_output = self.instrument.readParameter(55)

            if valve1_output is not None:
                current_valve_value = calculate_valve_percentage(valve1_output)
                self.update_inlet_valve_display(current_valve_value)
            else:
                # If read returns None (communication glitch)
                if hasattr(self.win, 'inlet_valve_label'):
                    self.win.inlet_valve_label.setText("...")

        except Exception as e:
            # If read throws an error
            print(f"Failed to perform initial valve read: {e}")
            if hasattr(self.win, 'inlet_valve_label'):
                self.win.inlet_valve_label.setText("...")


    def valve_close(self):
        print('Valve closed')
        self.win.label_valve_status.setText('Shut')
        #self.win.closeButton.setStyleSheet("background-color: red")
        #self.win.openButton.setStyleSheet("background-color: gray")
        self.flicker_timer.start(500)  # 500 ms interval
        self.instrument.writeParameter(12, 3)  # 'Valve Closed' command
        self.valve_status = "closed"

        # --- Disable Alarm ---
        try:
            # [cite_start]Mode 0: Off [cite: 1172]
            self.instrument.writeParameter(118, 0)
            print("Safety Alarm: DISABLED (Mode 0)")
        except Exception as e:
            print(f"Failed to disable alarm: {e}")
        # --------------------------

        if hasattr(self.win, 'inlet_valve_label'):
            self.win.inlet_valve_label.setStyleSheet("color: gray;")
            self.win.inlet_valve_label.setText("...")
        if hasattr(self.win, 'label_In_Out'):
            self.win.label_In_Out.setStyleSheet("color: gray;")

    def setPoint(self):
        # *** Guard against running while offline ***
        if self.is_offline or not self.connection_successful:
            print("Set point skipped: Device is offline.")
            return

        bar_setpoint = self.win.setpoint.value()

        self._handle_setpoint_safety_logic(bar_setpoint)

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

    def _reenable_alarm(self):
        """Re-enables the alarm if PID mode is still active."""
        if self.valve_status == "PID" and self.response_alarm_enabled:
            try:
                print("Cooldown finished: Re-enabling Safety Alarm (Mode 2)")
                self.instrument.writeParameter(118, 2)
            except Exception as e:
                print(f"Failed to re-enable alarm: {e}")

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
            self.label_win.valve_status.setText('Shut')


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
                self.win.label_valve_status.setText('Shut')
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
    CRITICAL_ALARM = QtCore.pyqtSignal(int)

    def __init__(self, parent, capacity, thread_sleep_time):
        super(THREADFlow, self).__init__(parent)
        self.parent = parent
        self.instrument = self.parent.instrument
        self.propar_to_bar_func = self.parent.propar_to_bar
        self.capacity = capacity
        self.stop = False
        self.thread_sleep_time = float(thread_sleep_time)

    def run(self):
        last_alarm_status = 0  # Track changes
        while not self.stop:
            # 1. Mark the start time of this cycle
            loop_start_time = time.time()

            try:
                # --- Perform all reads ---
                # This is the "Work" that causes latency (e.g., takes 0.05s)
                alarm_status = self.instrument.readParameter(28)
                raw_measure = self.instrument.readParameter(8)
                valve1_output = self.instrument.readParameter(55)

                # --- Offline Logic ---
                # If critical read fails (None), device is disconnected.
                if raw_measure is None:
                    self.DEVICE_STATUS_UPDATE.emit('offline')
                    # If offline, don't do drift calculation, just wait 1s and retry
                    time.sleep(1.0)
                    continue

                # --- Status Logic ---
                if alarm_status is not None:
                    # DEBUG: Print only if status changes or is critical
                    if alarm_status != last_alarm_status:
                        print(f" [ALARM CHANGE] Status Code: {alarm_status} (Binary: {bin(alarm_status)})")
                        last_alarm_status = alarm_status

                    if alarm_status & 1:
                        self.DEVICE_STATUS_UPDATE.emit('Error')
                    elif alarm_status & 2:
                        self.DEVICE_STATUS_UPDATE.emit('Warning')
                    else:
                        self.DEVICE_STATUS_UPDATE.emit('Normal')

                    if (alarm_status & 32) or (alarm_status & 8):
                        self.CRITICAL_ALARM.emit(alarm_status)
                # --- Emission Logic (Pressure) ---
                # We use the current time as the timestamp for the graph
                timestamp = time.time()
                bar_measure = self.propar_to_bar_func(raw_measure, self.capacity)
                self.MEAS.emit(timestamp, bar_measure)

                # --- Emission Logic (Valve) ---
                if valve1_output is not None:
                    # Ensure the helper function is accessible here
                    current_valve_value = calculate_valve_percentage(valve1_output)
                    self.VALVE1_MEAS.emit(current_valve_value)

                # --- SMART SLEEP (Drift Correction) ---
                # 1. Calculate how long the read/emit process took
                work_duration = time.time() - loop_start_time
                # 4. PRINT IT (Temporary Debug)
                #print(f"Hardware IO took: {work_duration:.4f} seconds")
                # 2. Calculate remaining time to match the configured thread_sleep_time
                sleep_time = self.thread_sleep_time - work_duration

                # 3. Only sleep if we have time left.
                # If work_duration > thread_sleep_time, the hardware is slower than the config,
                # so we run immediately without sleeping.
                if sleep_time > 0:
                    time.sleep(sleep_time)

            except Exception as e:
                self.DEVICE_STATUS_UPDATE.emit('offline')
                print(f"Error reading from instrument: {e}")
                # On exception, wait a safe fixed amount before retrying
                time.sleep(2.0)

        print('Measurement thread stopped.')

    def stopThread(self):
        self.stop = True


if __name__ == '__main__':
    appli = QApplication(sys.argv)
    appli.setStyleSheet(qdarkstyle.load_stylesheet())
    #appli.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())

    main_window = None
    APP_CONFIG = load_configuration()
    default_port = APP_CONFIG['Connection'].get('default_com_port', '')

    while True:  # Start the selection loop
        #available_ports = [port.device for port in serial.tools.list_ports.comports()]
        ports_objects = serial.tools.list_ports.comports()
        available_ports = [port.device for port in ports_objects]

        if not available_ports:
            QMessageBox.critical(None, "Connection Error",
                                 "No COM ports found. Please ensure your device is connected.")
            sys.exit()  # Exit if no ports are found at all

        # --- SORTING MAGIC ---
        # If the default port is in the list, move it to index 0
        if default_port in available_ports:
            available_ports.insert(0, available_ports.pop(available_ports.index(default_port)))

        selected_port, ok = QInputDialog.getItem(
            None, "Select COM Port",
            "Connect to Bronkhorst device on:",
            available_ports, 0, False
        )

        if ok and selected_port:
            print(f"Attempting to connect to {selected_port}...")
            # Create a temporary instance to check the connection
            main_window = Bronkhost(com=selected_port, config=APP_CONFIG)
            #main_window = Bronkhost(com=selected_port,name="LOA Pressure Control")

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

