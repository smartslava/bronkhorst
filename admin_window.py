from PyQt5.QtWidgets import QMainWindow, QApplication, QMessageBox
from PyQt5 import uic
import time

class AdminWindow(QMainWindow):
    def __init__(self, parent=None):
        super(AdminWindow, self).__init__(parent)
        uic.loadUi('admin_window.ui', self)
        self.setWindowTitle("Advanced Settings")
        # Store a reference to the main window to access the instrument
        self.main_window = parent

        # Connect the button (which is now in this window's UI)
        if hasattr(self, 'set_pid_button'):
            self.set_pid_button.clicked.connect(self.set_pid_parameters)

        # Read the current PID values when the window opens
        self.read_pid_parameters()

        if hasattr(self, 'force_open_button'):
            self.force_open_button.clicked.connect(self.valve_force_open)

    def read_pid_parameters(self):
        """Reads the current PID values from the instrument and updates the UI."""
        # Use the instrument from the main window
        instrument = self.main_window.instrument
        try:
            p_gain = instrument.readParameter(167)
            i_gain = instrument.readParameter(168)
            d_gain = instrument.readParameter(169)

            if p_gain is not None:
                self.p_gain_box.setValue(p_gain)
            if i_gain is not None:
                self.i_gain_box.setValue(i_gain)
            if d_gain is not None:
                self.d_gain_box.setValue(d_gain)

            print(f"Read PID values into admin panel: P={p_gain}, I={i_gain}, D={d_gain}")
        except Exception as e:
            print(f"Error reading PID parameters in admin panel: {e}")

    def set_pid_parameters(self):
        """Attempts a full sequence to unlock, write, and save new PID values."""
        instrument = self.main_window.instrument
        try:
            p_gain = self.p_gain_box.value()
            i_gain = self.i_gain_box.value()
            d_gain = self.d_gain_box.value()

            print("--- Attempting final save sequence ---")

            # --- Step 1: Set Control Mode to allow RS232 writes ---
            print("1. Setting device to RS232 control mode...")
            instrument.writeParameter(12, 18)
            time.sleep(0.1)

            # --- Step 2: Write the new PID values ---
            print("2. Writing new PID values...")
            instrument.writeParameter(167, p_gain)
            instrument.writeParameter(168, i_gain)
            instrument.writeParameter(169, d_gain)
            time.sleep(0.1)

            # --- Step 3: Force save with "initreset" command ---
            print("3. Sending 'Store Configuration' command (initreset)...")
            # According to other manuals, initreset (par 7) value 1 can store settings.
            instrument.writeParameter(7, 1)
            time.sleep(0.2)  # This command can take longer

            # --- Step 4: Return to default bus control mode ---
            print("4. Returning to default bus control mode...")
            instrument.writeParameter(12, 0)

            print(f"Set and saved new PID values: P={p_gain}, I={i_gain}, D={d_gain}")
            QMessageBox.information(self, "Success", "PID parameters have been updated and saved.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to set PID parameters.\n\nError: {e}")

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
            instrument.writeParameter(12, 8)  # 'Valve Forced Open' command

            # Update the state variable in the MAIN window instance
            self.main_window.valve_status = "force_open"
        else:
            # If the user clicks "No"
            print("Valve Force Open cancelled by user.")