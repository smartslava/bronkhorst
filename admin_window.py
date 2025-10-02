from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5 import uic


class AdminWindow(QMainWindow):
    def __init__(self, parent=None):
        super(AdminWindow, self).__init__(parent)
        # Load the UI file you just created
        uic.loadUi('admin_window.ui', self)

        # Connect your new buttons to their functions here
        self.some_admin_button.clicked.connect(self.do_admin_task)

    def do_admin_task(self):
        print("Performing an administrator task!")