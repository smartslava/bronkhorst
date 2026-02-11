"""
Qt logging bridge.
Emits a Qt signal for every logging record.
"""

# libraries
import logging
from PyQt6 import QtCore


class QtLogHandler(logging.Handler, QtCore.QObject):
    """Logging handler that emits log messages as Qt signals."""
    new_log = QtCore.pyqtSignal(str)

    def __init__(self):
        QtCore.QObject.__init__(self)
        logging.Handler.__init__(self)
        
        # Set formatter
        self.setFormatter(logging.Formatter("[%(levelname)s] %(message)s")) # [%(name)s]

    def emit(self, record: logging.LogRecord):
        msg = self.format(record)  # applies formatter
        self.new_log.emit(msg)     # emit message