from PyQt6.QtWidgets import QDialog
from PyQt6 import uic
from PyQt6.QtGui import QIcon
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
            <li>Configuration Initialization: On launch, the system parses config.ini using the configparser library. 
            It loads critical runtime parameters such as the thread polling interval (program refresh rate), 
            circular buffer size (plot history), plot styling (line colors), and the maximum pressure safety limit. 
            It also validates the data types (converting floats/integers) to prevent runtime errors.</li>
        </ul>
        
        <h4>User Tag</h4>
        <ul>
          <li>Displays the user tag from the device's memory for identification. It can be modified in Advanced Settings.</li>
        </ul>
        
        <h4>Monitors</h4>
        <ul>
          <li><b>Device Status:</b> Displays the current device status (Normal, Warning, Error).</li>
          <li><b>Actual Mode:</b> Displays the current control mode (e.g., PID, Shut).</li>
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
        </ul>
        <h4>Time Plot</h4>
        <ul>
        <li><b>History (s):</b> Set the desired total span of time visible in the plot window. The value is sent when you 
        press Enter or when the input box loses focus. The application's temporal memory is finite and determined by the
         product of the circular buffer capacity (max_history) and the thread polling interval (thread_sleep_time). 
         Once this limit is reached, the oldest data points are automatically discarded to make room for new measurements.</li>
        <li><b>Plot Button:</b> Opens a real-time graph of pressure (default: yellow) and setpoint (default: red) over time. The graph's 
        visual style is customizable via the config.ini file, where users can define specific hexadecimal color codes 
        (e.g., #FFFF00) to distinguish between the real-time pressure reading and the setpoint target. Data is acquired and stored 
        using absolute Unix timestamps (UTC) to ensure long-term consistency, while a custom axis renderer dynamically 
        converts these values to the local time zone for display.</li>
        <li><b>Right-Click Menu (Plot Window):</b> Right-clicking inside the plot window provides quick access to data handling features, including:
        <ul style="list-style-type: circle; margin-top: 5px;">
            <li><span style="font-weight: bold;">Export Data:</span> Save the entire history buffer (timestamps, pressure 
            measurements, setpoints) to a file (e.g., CSV). While the live graph displays familiar local time, the application 
            saves and stores all data using Unix timestamps (seconds since 1970) to ensure absolute precision and easy 
            export to analysis tools.</li>
            <li><span style="font-weight: bold;">Save Image:</span> Export the current plot view as an image file (e.g., PNG).</li>
        </ul>
    </li>
        </ul>
        
        
        <h4>Controls</h4>
        <ul>
        <li><b>P Set (bar):</b> Set the desired pressure in bar. The value is sent when user presses Enter or when the input box loses focus. 
        The maximum value is limited by the device capacity (physical limit) or the user-defined safety preset "max_set_pressure" in the config.ini file.</li>
        <li><b>Purge Button:</b> Activates the purge sequence: sets the pressure setpoint to 0.0 bar and switches the device 
        to PID mode, regardless of the current mode.</li>
        <li><b>Valve Mode Radio Buttons:</b> The <b>PID</b> button enables automatic control, while the <b>Shut</b> button 
        fully closes both the input and output valves.</li>
        <li><b>Advanced Button:</b> Opens a password-protected panel for advanced settings. The password can be modified in the config.ini file.</li>
        </ul>
        
        <h4>Advanced Settings</h4>
        <p>This panel is accessed via the 'Advanced' button and requires a password. The password can be modified in the config.ini file. 
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
          <li><b>UserTag: </b> User definable alias string. Maximum 16 characters allow the user to give the instrument his own tag name.</li>
        </ul>
        """
        version_info = f"""
               <hr>
               <p style='text-align:left; color:gray;'>
                   <i>Version: {self.version}</i>
               </p>
               <hr>
               """

        self.help_text_edit.setHtml(version_info+help_text)