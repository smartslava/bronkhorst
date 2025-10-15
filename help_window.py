from PyQt5.QtWidgets import QDialog
from PyQt5 import uic
from PyQt5.QtGui import QIcon
import pathlib, os


class HelpWindow(QDialog):
    def __init__(self, version="N/A", parent=None):
        super(HelpWindow, self).__init__(parent)
        uic.loadUi('help_window.ui', self)
        self.version = version
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
        <p>
            This application controls a Bronkhorst EL-PRESS P-800 series pressure controller. 
            The P-800 controller incorporates two control valves: an inlet and a relief valve. 
            Opening the inlet valve increases the pressure in the outgoing conduit, while opening the relief valve decreases it. 
            A pressure sensor measures the pressure in the conduit, providing input for a controller that drives both valves.
        </p>
        
        <h4>General Behaviour</h4>
        <ul>
            <li>Upon startup, the program prioritizes safety by immediately <b>sending a command to close the inlet valve</b> and then queries the device to <b>read and display the last known setpoint</b>.</li>
            <li>The setpoint value can be modified even while the valve is closed, allowing the user to prepare the next setting in advance.</li>
            <li>To ensure a safe state upon exit, the application again sends a command to <b>close the valve</b> before terminating the connection.</li>
        </ul>
        
        <h4>Monitors</h4>
        <ul>
          <li><b>Actual Mode:</b> Displays the current control mode (e.g., Closed, PID).</li>
          <li><b>In/Out Status (%):</b> Shows the real-time opening of the P-800's two control valves - an inlet (In) and a relief (Out). The percentage corresponds to:
            <ul>
              <li><b>Above 50%:</b> The inlet valve is opening.</li>
              <li><b>Exactly 50%:</b> Both valves are closed.</li>
              <li><b>Below 50%:</b> The relief valve is opening.</li>
            </ul>
            <small><i>Note: The "..." value shown during "Closed Mode" can be ignored.</i></small>
            <small><i>Sometimes shows 0% while both valves are closed, need to debug...</i></small>
          </li>
          <li><b>Actual P (bar):</b> Displays the real-time pressure measured by the controller.</li>
          <li><b>Time Plot Button:</b> Opens a real-time graph of pressure (yellow) and setpoint (red) over time.</li>
        </ul>
        
        <h4>Controls</h4>
        <ul>
        <li><b>P Set (bar):</b> Set the desired pressure in bar. The value is sent when you press Enter or when the input box loses focus.</li>
        <li><b>Valve Mode Buttons:</b> The <b>PID</b> button enables automatic control, while the <b>Closed</b> button fully closes the inlet valve.</li>
        <li><b>Advanced Button:</b> Opens a password-protected panel for advanced settings.</li>
        </ul>
        
        <h4>Advanced Settings</h4>
        <p>This panel is accessed via the 'Advanced' button and requires a password. 
        Upon opening, the software reads and displays the following settings from the device. 
        After editing the values, press the 'SET ALL' button to save them back to the device:</p>
        <ul>
          <li><b>Kp:</b> (Proportional Gain) Proportional action, multiplication factor. The default value is <b>2000</b>.</li>
          <li><b>Ti:</b> (Integral Gain) Integration action in seconds. The default value is <b>0.25</b>.</li>
          <li><b>Td:</b> (Derivative Gain) Differentiation action in seconds. The default value is <b>0.0</b>.</li>
          <li><b>Kspeed:</b> (Controller Speed) A factor by which the Proportional Gain (Kp) is multiplied. The default value is <b>1.0</b>.</li>
          <li><b>Kopen:</b> (Open from Zero Response) Adjusts the controller response when starting from 0%. A value of 128 means no correction, while other values adjust the speed by a factor of 1.05^(128-Kopen). The default is <b>128</b>.</li>
          <li><b>Knorm:</b> (Normal Step Response) Adjusts the controller response during a normal setpoint step. A value of 128 means no correction, while other values adjust the speed by a factor of 1.05^(128-Knorm). The default is <b>128</b>.</li>
          <li><b>Kstab:</b> (Stable Response) Adjusts the controller response when stable (within a 2% band). A value of 128 means no correction, while other values adjust the speed by a factor of 1.05^(128-Kstab). The default is <b>128</b>.</li>
          <li><b>Hyster: </b> (Controller Hysteresis) Defines a pressure band around the setpoint where both control valves remain closed. The value (0 to 1.0) corresponds to 0% to 100% of the setpoint range. The default is <b>0.001 (0.1%)</b>.</li>
        </ul>
        """
        version_info = f"""
               <hr>
               <p style='text-align:left; color:gray;'>
                   <i>Version: {self.version}</i>
               </p>
               """

        self.help_text_edit.setHtml(version_info+help_text)