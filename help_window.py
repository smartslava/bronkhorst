from PyQt5.QtWidgets import QDialog
from PyQt5 import uic
from PyQt5.QtGui import QIcon
import pathlib, os


class HelpWindow(QDialog):
    def __init__(self, parent=None):
        super(HelpWindow, self).__init__(parent)
        uic.loadUi('help_window.ui', self)
        p = pathlib.Path(__file__)
        sepa = os.sep
        self.icon = str(p.parent) + sepa + 'icons' + sepa
        self.setWindowTitle("Application Help")
        self.setWindowIcon(QIcon(self.icon + 'LOA3.png'))
        self._populate_text()

    def _populate_text(self):
        # You can use simple HTML for formatting
        help_text = """
        <h2>LOA GAS Pressure Control</h2>
        <p>This application controls a Bronkhorst EL-PRESS pressure controller.</p>
        
        <h4>General Behaviour</h4>
        <ul>
            <li>Upon startup, the program prioritizes safety by immediately <b>sending a command to close the inlet valve</b> and then queries the device to <b>read and display the last known setpoint</b>.</li>
            <li>The setpoint value can be modified even while the valve is closed, allowing the user to prepare the next setting in advance.</li>
            <li>To ensure a safe state upon exit, the application again sends a command to <b>close the valve</b> before terminating the connection.</li>
        </ul>
        
        <h4>Monitors</h4>
        <ul>
          <li><b>Valve Status:</b> Displays the current state of the inlet valve (e.g., Closed, PID Control, Open).</li>
          <li><b>Valve Opening (%):</b> Displays the real-time opening of the inlet valve as a percentage.</li>
          <li><b>Actual P (bar):</b> Displays the pressure measured by the controller in bar.</li>
          <li><b>Plot Button:</b> Opens a real-time graph of pressure over time.</li>
        </ul>
        
        <h4>Controls</h4>
        <ul>
          <li><b>P Set (bar):</b> Sets the desired pressure in bar. The value is sent when you press Enter or when the input box loses focus.</li>
          <li><b>PID/Close Buttons:</b> Enables PID control or fully closes the inlet valve.</li>
          <li><b>Advanced Button:</b> Opens a password-protected panel for advanced settings.</li>
        </ul>
        
        <h4>Advanced Settings</h4>
        <p>This panel is accessed via the 'Advanced' button and requires a password. It contains the following settings:</p>
        <ul>
          <li><b>PID Tuning:</b> Allows for changing the P, I, and D gains. Changes must be explicitly saved to the device to be permanent (NOT IMPLEMENTED!).</li>
          <li><b>Valve Force Open:</b> Bypasses safety controls to fully open the valve. A confirmation is required.</li>
        </ul>
        """
        self.help_text_edit.setHtml(help_text)