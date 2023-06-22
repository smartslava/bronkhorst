# -*- coding: utf-8 -*-
"""
Created on Wed Jun 21 15:26:36 2023

@author: SALLEJAUNE
"""

import propar
from PyQt5 import QtCore,uic
from PyQt5.QtWidgets import QApplication,QWidget,QMainWindow
from PyQt5.QtGui import QIcon
import sys
import time
import qdarkstyle
from PyQt5.QtCore import Qt
import pathlib,os

class Bronkhost(QMainWindow):
    
    def __init__(self,com='com7',name='XRL',parent=None):
       
        super(Bronkhost,self).__init__(parent)
        p = pathlib.Path(__file__)
        sepa=os.sep
        self.win=uic.loadUi('flow.ui',self)
        self.instrument = propar.instrument(com)
        self.setWindowTitle(name)
        self.icon=str(p.parent) + sepa+'icons'+sepa
        self.setWindowIcon(QIcon(self.icon+'LOA.png'))
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.raise_()
        
        self.instrument.writeParameter(12, 3)
        self.win.measure.setText('Valve closed')
        self.win.measure.setStyleSheet("color: red")
        
        self.closed=True
        self.actionButton()
        self.threadFlow=THREADFlow(self)
        self.threadFlow.start()
        self.threadFlow.MEAS.connect(self.aff)
        self.win.title_2.setText(name+' Flow Gas Control')
    
    def actionButton(self):
        self.win.openButton.clicked.connect(self.open)
        self.win.closeButton.clicked.connect(self.close)
        self.win.setpoint.editingFinished.connect(self.setPoint)
        self.win.dial.valueChanged.connect(self.dialMoved)
        self.win.fullyOpen.clicked.connect(self.full)
        

    def full(self):
        print('open')
        self.win.fullyOpen.setStyleSheet("background-color: green")
        self.win.closeButton.setStyleSheet("background-color:gray")
        self.instrument.writeParameter(12, 8)
        self.closed='Full'
        self.win.measure.setText("Fully Open")
        self.win.measure.setStyleSheet("color: white")

    def open(self):
        print('open')
        self.win.openButton.setStyleSheet("background-color: green")
        self.win.closeButton.setStyleSheet("background-color:gray")
        self.win.fullyOpen.setStyleSheet("background-color: gray")
        self.instrument.writeParameter(12, 0)
        self.closed=False
        self.win.measure.setStyleSheet("color: white")
        
    def close(self):
        print('close')
        self.win.closeButton.setStyleSheet("background-color: red")
        self.win.openButton.setStyleSheet("background-color: gray")
        self.win.fullyOpen.setStyleSheet("background-color: gray")
        self.instrument.writeParameter(12, 3)
        self.closed=True
        self.win.measure.setStyleSheet("color: red")
        
    def setPoint(self):
        print (str(self.win.setpoint.value()))
        self.win.dial.setValue(int(self.win.setpoint.value()))
       
       # Measure and setpoint scaled to 0-32000 = 0-100%
        para=int(self.win.setpoint.value()*32000/100)
        self.instrument.writeParameter(9, para)
        
    def dialMoved(self):
        a=self.win.dial.value()
        para=int(self.win.dial.value()*32000/100)
        self.win.setpoint.setValue(a)
        self.instrument.writeParameter(9, para)
    
    def aff(self,M):
        print(self.closed)
        if self.closed==False:
            s=round(float(M),1)
            self.win.measure.setText(str(s))
        elif self.closed=='Full':
            self.win.measure.setText("Fully Open")
        else :
            self.win.measure.setText('Valve closed')
     
    def closeEvent(self,event):
        
        self.threadFlow.stopThread()
        self.instrument.writeParameter(12, 3)
        self.win.measure.setText('Valve closed')
        self.win.measure.setStyleSheet("color: red")
        time.sleep(0.5)
        self.instrument.master.propar.stop() # stop the port communication
        time.sleep(0.5)
        event.accept()
        
class THREADFlow(QtCore.QThread) :  
    
    
    MEAS=QtCore.pyqtSignal(float)
    
    def __init__(self,parent):
        super(THREADFlow,self).__init__(parent)
        self.parent=parent
        self.instrument=self.parent.instrument
        self.stop=False
        
    def run(self) :
        while True:
            if self.stop==True:
                print('stop thread')
                break
            pressure=float(self.instrument.readParameter(8)*100/32000)
            self.MEAS.emit(pressure)
            time.sleep(0.5)
            
            
            
    def stopThread(self):
         self.stop=True
         
if __name__=='__main__'  :
    appli=QApplication(sys.argv)
    appli.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    xuv=Bronkhost(com='com7')
    # hhg=Bronkhost(com='com4', name='HHG')
    # hhg.show()
    xuv.show()
    appli.exec_()
    