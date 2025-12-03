from PyQt6.QtWidgets import (QDialog, QWidget, QHBoxLayout, QLineEdit,
                             QPushButton, QLabel, QVBoxLayout)
from PyQt6 import uic
from PyQt6.QtGui import QIcon, QShortcut, QKeySequence, QTextDocument, QTextCursor
from PyQt6.QtCore import Qt
import pathlib, os


class HelpWindow(QDialog):
    def __init__(self, version="N/A", parent=None):
        super(HelpWindow, self).__init__(parent)

        # 1. Load the UI
        uic.loadUi('help_window.ui', self)
        self.help_text_edit.setStyleSheet("selection-background-color: #FFFF00; selection-color: #000000;")
        # 2. Setup Basic Info
        self.version = version
        p = pathlib.Path(__file__)
        sepa = os.sep
        self.icon = str(p.parent) + sepa + 'icons' + sepa
        self.setWindowTitle("Application Help")
        self.setWindowIcon(QIcon(self.icon + 'LOA3.png'))

        # 3. Populate Content
        self._populate_text()

        # 4. Initialize the Search Feature
        self._init_search_ui()

    def _init_search_ui(self):
        """
        Creates a hidden search bar at the bottom of the layout
        and sets up the Ctrl+F shortcut.
        """
        # --- A. Create the Search Widget Wrapper ---
        self.search_widget = QWidget(self)
        self.search_layout = QHBoxLayout(self.search_widget)
        self.search_layout.setContentsMargins(0, 5, 0, 0)

        # --- B. Create UI Elements ---
        self.search_label = QLabel("Find:", self.search_widget)
        self.search_input = QLineEdit(self.search_widget)
        self.search_input.setPlaceholderText("Type text...")
        self.search_input.setFixedWidth(200)

        self.btn_next = QPushButton("Next", self.search_widget)
        self.btn_prev = QPushButton("Prev.", self.search_widget)
        self.btn_close = QPushButton("X", self.search_widget)
        self.btn_close.setFixedWidth(30)
        self.btn_close.setStyleSheet("color: red; font-weight: bold;")

        # --- C. Add Elements to Search Layout ---
        self.search_layout.addWidget(self.search_label)
        self.search_layout.addWidget(self.search_input)
        self.search_layout.addWidget(self.btn_next)
        self.search_layout.addWidget(self.btn_prev)
        self.search_layout.addStretch()  # Push everything to the left
        self.search_layout.addWidget(self.btn_close)

        # --- D. Insert into Main Layout ---
        # IMPORTANT: This assumes your help_window.ui has a vertical layout.
        # If self.layout() is None, we create one.
        if self.layout() is None:
            main_layout = QVBoxLayout(self)
            # If you had widgets with absolute positioning, this might shift them.
            # Assuming standard Designer usage:
            if hasattr(self, 'help_text_edit'):
                main_layout.addWidget(self.help_text_edit)
            self.setLayout(main_layout)

        # Add the search widget to the bottom of the dialog
        self.layout().addWidget(self.search_widget)

        # Hide it by default
        self.search_widget.hide()

        # --- E. Connect Signals ---
        self.btn_next.clicked.connect(lambda: self.find_text(direction='next'))
        self.btn_prev.clicked.connect(lambda: self.find_text(direction='prev'))
        self.btn_close.clicked.connect(self.search_widget.hide)

        # Search when pressing Enter in the box
        #self.search_input.returnPressed.connect(lambda: self.find_text(direction='next'))
        # Hide when pressing Escape in the box
        self.escape_shortcut = QShortcut(QKeySequence("Esc"), self.search_widget)
        self.escape_shortcut.activated.connect(self.search_widget.hide)

        # --- F. Create Global Ctrl+F Shortcut ---
        self.find_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.find_shortcut.activated.connect(self.show_search_bar)

    def show_search_bar(self):
        """Shows the search bar and focuses the input field."""
        self.search_widget.show()
        self.search_input.setFocus()
        self.search_input.selectAll()

    def find_text(self, direction='next'):
        """
        Search for text. If it hits the end/start, it wraps around automatically.
        """
        search_term = self.search_input.text()
        if not search_term:
            return

        # Configure Find Flags
        flags = QTextDocument.FindFlag(0)  # Default is 0 (Forward)

        if direction == 'prev':
            flags = QTextDocument.FindFlag.FindBackward

        # --- 1. Attempt Search from current cursor position ---
        found = self.help_text_edit.find(search_term, flags)

        # --- 2. If not found, Wrap Around and search again ---
        if not found:
            # Move cursor to the opposite end of the document to restart search
            if direction == 'prev':
                # If going back and hit top, go to bottom
                self.help_text_edit.moveCursor(QTextCursor.MoveOperation.End)
            else:
                # If going forward and hit bottom, go to top
                self.help_text_edit.moveCursor(QTextCursor.MoveOperation.Start)

            # Try finding again from the new position
            found = self.help_text_edit.find(search_term, flags)

        # --- 3. Visual Feedback ---
        if not found:
            # If STILL not found (meaning the word isn't in the doc at all)
            self.search_input.setStyleSheet("background-color: #ffcccc; color: black;")  # Red
        else:
            self.search_input.setStyleSheet("")  # Normal / White

    def keyPressEvent(self, event):
        """
        Intercepts key presses to prevent Enter from closing the dialog
        only when the search box is focused.
        """
        # 1. Check if the key pressed is Enter or Return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):

            # 2. Check if the Search Input has focus
            if self.search_input.hasFocus():
                # Run the search logic
                self.find_text(direction='next')

                # 'accept' tells Qt "I handled this, stop processing."
                # This prevents the signal from reaching the QDialog close handler.
                event.accept()
                return

        # 3. For all other keys (like Esc), let QDialog handle them normally
        super().keyPressEvent(event)

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
                <li><b>Startup Safety:</b> Upon startup, the program prioritizes safety by immediately <b>sending a command to close both the inlet and relief valves</b>. It then queries the device to <b>read and display the last known setpoint</b>.</li>
                <li><b>Setpoint Pre-configuration:</b> The setpoint value can be modified even while  valves are closed, allowing the user to prepare the next setting in advance.</li>
                <li><b>Exit Safety:</b> To ensure a safe state upon exit, the application sends a final command to <b>close valves</b> before terminating the connection.</li>
                <li><b>Configuration Initialization:</b> On launch, the system parses <code>config.ini</code> to load critical runtime parameters such as the thread polling interval, plot history size, and maximum pressure limits. 
                <br><i>(Please refer to the <b>Configuration File</b> at the bottom of this text for a detailed description of all settings.)</i></li>
            </ul>
            
            <h4>Important Observation</h4> 
            <ul> <li><b>Internal Leakage:</b> 
            When the system is in <b>Shut Mode</b> (both valves closed) while pressurized, a minor internal leak into the conduit may occur. 
            For example, an inlet pressure of 100 bar can raise the conduit pressure by a few bars over several hours. 
            The rate of this leakage may vary depending on the specific valve unit.</li> </ul>
            
            
<h4>Deviation Safety Protocol</h4> 
<ul> 
    <li><b>Active Monitoring:</b> When PID control is active, the system 
    enables a hardware-level alarm (Response Alarm Mode 2) to monitor pressure deviation against the 
    <b>tolerance limit</b> defined in the config.</li> 

    <li><b>Transient Protection:</b> 
    To prevent false alarms during intentional pressure drops, the system compares the 
    <b>Current Pressure</b> against the <b>New Setpoint</b>. If the pressure is currently unsafe 
    (higher than the new Setpoint + Tolerance), the alarm is temporarily paused (Cooldown) to allow 
    the pressure to stabilize downwards without triggering a fault.
    </li> 

    <li><b>Immediate Reaction:</b> If the measured pressure exceeds the threshold (Setpoint + Tolerance) 
    while the alarm is active, the device <b>automatically triggers the Safety Purge Protocol</b>.</li> 

    <li><b>Safety Purge Protocol:</b> 
    The software takes control to safely vent the system. It sets the target pressure to <b>0.0 bar</b> 
    and monitors the drop. The system will <b>automatically close valves</b> 
    as soon as the pressure reaches the safe target (0.0 bars + Tolerance), OR if the safety configurable timeout (<i>purge_shut_delay_timeout</i>) expires.
    </li> 

    <li><b>Operator Alert:</b> 
    A diagnostic popup is displayed to notify the user that an automatic safety shutdown (Safety Purge) has occurred, 
    including the diagnostic code.</li> 
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
        visual style is customizable via the <code>config.ini</code> file, where users can define specific hexadecimal color codes 
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
        The maximum value is limited by the device capacity (physical limit) or the user-defined safety preset "max_set_pressure" in the <code>config.ini</code> file.</li>
        <li><b>Purge Button:</b> Activates the purge sequence: Sets the setpoint to the <b>configured purge pressure</b> (default 0.0 bar) 
        and switches the device to <b>PID mode</b>. It monitors the pressure drop and <b>automatically closes valves</b> 
        once the target is reached or the safety timeout expires.</li>
        <li><b>Valve Mode Radio Buttons:</b> The <b>PID</b> button enables automatic control, while the <b>Shut</b> button 
        fully closes both the input and relief valves.</li>
        <li><b>Advanced Button:</b> Opens a password-protected panel for advanced settings. The password can be modified in the <code>config.ini</code> file.</li>
        </ul>
        
        <h4>Advanced Settings</h4>
        <p>This panel is accessed via the 'Advanced' button and requires a password. The password can be modified in the <code>config.ini</code> file. 
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
        <hr>
        <h2>Configuration Guide (<code>config.ini</code>)</h2>
        <p>The application behavior is controlled by the <code>config.ini</code> file located in the program folder. Below is a reference for the available settings.</p>
        
        
        
        <h3>[Safety]</h3>
        <p>Critical settings for device limits and automatic safety protocols.</p>
        <ul>
            <li><span class="param">max_set_pressure:</span> The absolute maximum pressure (bar) the user can enter in the UI. If this exceeds the physical device limit, the device limit is used.</li>
           <li><span class="param">purge_shut_delay_timeout:</span> The <b>maximum duration</b> (seconds) the system will 
           attempt to reach the purge target pressure. If the target is reached sooner, the valves close immediately; 
           otherwise, the system forces a shutdown once this timer expires.</li>
            <li><span class="param">set_point_above_safety_enable:</span> Master switch for the Deviation Alarm (1 = On, 0 = Off).</li>
            <li><span class="param">set_point_above_tolerance:</span> The allowed deviation (in bar) above the current setpoint. If <i>Measure > Setpoint + Upper Tolerance</i>, the alarm triggers. Tolerance below the setpoint is ignored.</li>
            <li><span class="param">set_point_above_delay:</span> Duration (seconds) the high pressure must persist before the safety shutdown is triggered.</li>
           <li><span class="param">set_point_lower_cooldown_delay:</span> The duration (seconds) of the safety grace period. 
           The alarm is deactivated for this interval when lowering the setpoint or purging; if the pressure remains larger than <b>Target Setpoint</b> + Tolerance after this time, 
           the grace period <b>extends automatically</b> until safe.</li>
        </ul>
        
        <h3>[Connection]</h3>
        <ul>
            <li><span class="param">default_com_port:</span> The COM port selected by default in the connection dialog (e.g., COM6).</li>
        </ul>

        <h3>[Thread]</h3>
        <ul>
            <li><span class="param">thread_sleep_time:</span> The interval (seconds) between measurement updates. <span class="note">(Min recommended: 0.05s)</span>.</li>
        </ul>
        
        <h3>[Plotting]</h3>
        <ul>
            <li><span class="param">max_history:</span> The maximum number of data points kept in memory buffer.</li>
            <li><span class="param">default_duration:</span> The default time range (seconds) visible on the X-axis when the app starts.</li>
            <li><span class="param">pressure_color / setpoint_color:</span> Hex codes for the plot lines (e.g., #FFFF00).</li>
        </ul>
        
    
        <h3>[Security]</h3>
        <ul>
            <li><span class="param">admin_password:</span> Password required to access the Admin Panel.</li>
        </ul>
        
        
        
        <h3>[UI]</h3>
        <ul>
            <li><span class="param">window_title:</span> The text displayed in the main application window title bar.</li>
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