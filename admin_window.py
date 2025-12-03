from PyQt6.QtWidgets import QMainWindow, QApplication, QMessageBox
from PyQt6 import uic
import time

class AdminWindow(QMainWindow):
    def __init__(self, parent=None):
        super(AdminWindow, self).__init__(parent)
        uic.loadUi('admin_window.ui', self)
        self.setWindowTitle("Advanced Settings")
        # Store a reference to the main window to access the instrument
        self.main_window = parent

        # --- Set tooltips for parameter explanations ---
        self.p_gain_box.setToolTip(
            "<b>Proportional Gain (Kp)</b><br>Proportional action, multiplication factor. (float:0...1e+10) Default: 2000")
        self.i_gain_box.setToolTip(
            "<b>Integral Gain (Ti)</b><br>Integration action in seconds. (float:0...1e+10) Default: 0.25")
        self.d_gain_box.setToolTip(
            "<b>Derivative Gain (Td)</b><br>Differentiation action in seconds. (float:0...1e+10) Default: 0.0")
        self.speed_gain_box.setToolTip(
            "<b>Controller Speed (Kspeed)</b><br>Controller speed factor. PID-Kp is multiplied by this factor (float:0...3.40282E+38). Default: 1.0")
        self.open_gain_box.setToolTip(
            "<b>Open from Zero Response (Kopen)</b><br>Controller response when starting-up from 0%. Kopen, Kp multiplication factor when valve opens. Value 128 means no correction. Otherwise controller speed will be adjusted by a factor 1.05^(128-Kopen) (int:0...255). Default: 128")
        self.norm_gain_box.setToolTip(
            "<b>Normal Step Response (Knorm)</b><br>Controller response during normal control. Knormal, Kp multiplication factor at setpoint step. Value 128 means no correction. Otherwise controller speed will be adjusted by a factor 1.05^(128-Knorm) (int:0...255). Default: 128")
        self.stab_gain_box.setToolTip(
            "<b>Stable Response (Kstab)</b><br>Controller response when controller is stable. Kstable, Kp multiplication factor within band of 2%. Value 128 means no correction. Otherwise controller speed will be adjusted by a factor 1.05^(128-Kstab) (int:0...255). Default: 128")
        self.hyster_gain_box.setToolTip(
            "<b>Controller Hysteresis</b><br>Defines a pressure band around the setpoint where both control valves stay closed. This state becomes active when the setpoint is reached and remains active as long as the measured pressure remains within the specified bandwidth. The supported value range 0 to 1.0 corresponds with (0 to 100%) of the setpoint range. (float:0...1) Default: 0.001 (0.1%).")
        # Connect the button (which is now in this window's UI)
        if hasattr(self, 'set_pid_button'):
            self.set_pid_button.clicked.connect(self.set_pid_parameters)

        # Read the current PID values when the window opens
        self.read_pid_parameters()

    def read_pid_parameters(self):
        """Reads the current PID values from the instrument and updates the UI."""
        instrument = self.main_window.instrument

        # 1. Initialize variables to None
        # (Prevents "UnboundLocalError" if the try block crashes early)
        p_gain = i_gain = d_gain = speed_gain = None
        open_gain = norm_gain = stab_gain = hyster_gain = user_tag_raw = None
        user_tag = "Unknown"

        # 2. Hardware Read (LOCKED)
        self.main_window.instrument_mutex.lock()
        try:
            p_gain = instrument.readParameter(167)
            i_gain = instrument.readParameter(168)
            d_gain = instrument.readParameter(169)
            speed_gain = instrument.readParameter(254)
            open_gain = instrument.readParameter(165)
            norm_gain = instrument.readParameter(72)
            stab_gain = instrument.readParameter(141)
            hyster_gain = instrument.readParameter(361)
            user_tag_raw = instrument.readParameter(115)
        except Exception as e:
            print(f"Hardware read failed: {e}")
        finally:
            self.main_window.instrument_mutex.unlock()

        # 3. UI Update (Safe to do unlocked)
        try:
            if p_gain is not None: self.p_gain_box.setValue(p_gain)
            if i_gain is not None: self.i_gain_box.setValue(i_gain)
            if d_gain is not None: self.d_gain_box.setValue(d_gain)
            if speed_gain is not None: self.speed_gain_box.setValue(speed_gain)
            if open_gain is not None: self.open_gain_box.setValue(open_gain)
            if norm_gain is not None: self.norm_gain_box.setValue(norm_gain)
            if stab_gain is not None: self.stab_gain_box.setValue(stab_gain)
            if hyster_gain is not None: self.hyster_gain_box.setValue(hyster_gain)

            # Logic Fix: Only convert user_tag if it's not None
            if user_tag_raw is not None:
                user_tag = str(user_tag_raw)
                self.user_tag_lineedit.setText(user_tag.strip())

            # --- RESTORED PRINT STATEMENT ---
            print(
                f"Read valve control parameters: Kp={p_gain}, Ti={i_gain}, Td={d_gain}, Kspeed={speed_gain}, Kopen={open_gain}, Knormal={norm_gain}, Kstable={stab_gain}, Hysteresis={hyster_gain}, UserTag={user_tag}")

        except Exception as e:
            print(f"Error updating UI: {e}")

    def set_pid_parameters(self):
        """Attempts a full sequence to unlock, write, and save new PID values."""
        instrument = self.main_window.instrument
        try:
            p_gain = self.p_gain_box.value()
            i_gain = self.i_gain_box.value()
            d_gain = self.d_gain_box.value()
            speed_gain = self.speed_gain_box.value()
            open_gain = self.open_gain_box.value()
            norm_gain = self.norm_gain_box.value()
            stab_gain = self.stab_gain_box.value()
            hyster_gain = self.hyster_gain_box.value()
            user_tag = self.user_tag_lineedit.text().strip()

            print("--- Attempting control parameters save sequence ---")

            # --- Step 1: Set Control Mode to allow RS232 writes ---
            print("Setting device to initreset: enable changes mode...")
            self.main_window.instrument_mutex.lock()  # <--- ADD LOCK
            try:
                instrument.writeParameter(7, 64)
                #time.sleep(0.1)
                # --- Step 2: Write the new PID values ---
                print("2. Writing new control values...")
                instrument.writeParameter(167, p_gain)
                instrument.writeParameter(168, i_gain)
                instrument.writeParameter(169, d_gain)
                instrument.writeParameter(254, speed_gain)
                instrument.writeParameter(165, int(open_gain))
                instrument.writeParameter(72, int(norm_gain))
                instrument.writeParameter(141, int(stab_gain))
                instrument.writeParameter(361, hyster_gain)
                instrument.writeParameter(115, user_tag)
                #time.sleep(0.1)
                print("Setting device to initreset: disable changes mode...")
                instrument.writeParameter(7, 0)
                #time.sleep(0.1)
            finally:
                self.main_window.instrument_mutex.unlock()
            print(f"Set and saved new control values: Kp={p_gain}, Ti={i_gain}, Td={d_gain}, Kspeed={speed_gain},Kopen={open_gain}, Knormal={norm_gain},Kstable={stab_gain},Hysteresis={hyster_gain},UserTag={user_tag}")

            #QMessageBox.information(self, "Success", "Control parameters have been updated.")

            try:
                self.main_window.read_device_info()
                print("Control parameters have been updated.")
                print("Main window device info refreshed after saving settings.")
            except Exception as e:
                print(f"Warning: could not refresh device info after saving: {e}")


        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to set control parameters.\n\nError: {e}")
            print( "Error:Failed to set control parameters. Error: ",e)

    def valve_force_open(self):
        # Create the warning message box
        reply = QMessageBox.warning(self,
                                    'Confirm Action',
                                    '<b>Warning:</b> You are about to force the inlet valve completely open. <br><br>The pressure can rise to dangerous levels without any control! <br><br>Are you sure you want to proceed?',
                                    QMessageBox.Yes | QMessageBox.No,
                                    QMessageBox.No)  # Default button is 'No'

        # Check if the user clicked the "Yes" button
        if reply == QMessageBox.Yes:
            print("User confirmed. Forcing valve open from admin panel.")

            # --- This is your existing code, which now runs only on confirmation ---
            instrument = self.main_window.instrument
            main_ui = self.main_window.win

            # Update status label and OTHER buttons on the MAIN window
            main_ui.label_valve_status.setText('Force Opened')
            main_ui.openButton.setStyleSheet("background-color: gray;")
            main_ui.closeButton.setStyleSheet("background-color: gray;")

            # Update the button on THIS admin window
            self.force_open_button.setStyleSheet("background-color: red;")

            # Send the command to the instrument
            self.main_window.instrument_mutex.lock()  # <--- ADD LOCK
            try:
                instrument.writeParameter(12, 8)  # 'Valve Forced Open' command
            finally:
                self.main_window.instrument_mutex.unlock()

            # Update the state variable in the MAIN window instance
            self.main_window.valve_status = "force_open"
        else:
            # If the user clicks "No"
            print("Valve Force Open cancelled by user.")