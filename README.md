# bronkhorst
Gui to use bronkhosrt gas controler  www.bronkhorst.com
using :https://github.com/bronkhorst-developer/bronkhorst-propar
 
*   python 3.x
*   PyQt6
*   propar (pip install bronkhorst-propar)
*   qdarkstyle (https://github.com/ColinDuquesnoy/QDarkStyleSheet.git)

  
  ## Usages   
  appli = QApplication(sys.argv)    
  appli.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())     
  e = bronkhost(com='your port com',name='your name'    
  e.show()   
  appli.exec_()    
  
 
