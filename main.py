from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtDBus import *
from yeni_rifki3 import Ui_MainWindow as Page1
from processRifki import Ui_MainWindow as Page2
from warningStep1 import Ui_Dialog as Step1
from warningStep2 import Ui_Dialog as Step2
from lastQuestion import Ui_Dialog as lastQuestion_
import sys
import os
import dbus
from functools import partial
import gi
gi.require_version('UDisks', '2.0')
from gi.repository import UDisks
from device_process import *
#import gobject

  
class main(QMainWindow):
    
    app = QApplication([])
    
    def __init__(self, parent=None):
        super(main, self).__init__(parent)
        self.targetDevice = None
        self.targetIso = None
        self.bus = dbus.SessionBus()
        self.udisks_client = UDisks.Client.new_sync()
        self.udisk_listener_id = self.udisks_client.connect("changed", self.deviceDetect)
        self.ui = Page1()
        self.ui.setupUi(self)
        #self.ui.start.clicked.connect(self.page2)
        self.ui.isoSelect.clicked.connect(self.selectTheISO)
        self.ui.usbSelect.clicked.connect(self.selectTheDevice)
        self.ui.start.clicked.connect(self.controlState)
        self.show()
        self.deviceDetect()
        sys.exit(self.app.exec_())

    def okBtn(self, k):
        self.workId = 1
        k.close()

    def page2(self):
        a = QDialog()
        self.workId = None
        answerControl = lastQuestion_()
        answerControl.setupUi(a)
        cancelBtn = lambda: a.close()
        answerControl.ok.clicked.connect(partial(self.okBtn, a))
        answerControl.cancel.clicked.connect(cancelBtn)

        a.exec_()

        if self.workId==1:
            print("Ok a basıldı") 
            self.ui = Page2()
            self.ui.setupUi(self)
            
        else:
            print("bir sey lmadı")
            return #a.close()
        self.udisks_client.disconnect_by_func(self.deviceDetect)    
        _, name = os.path.split(self.targetDevice)
        management = DeviceManage(name)
        management.do_umount()
        management.do_format()
        #management.do_mount()
        stateProcess =  ExtractProcessControl(self.ui, self.targetIso)
        stateProcess.extractall(self.targetDevice)


    def selectTheISO(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, _ = QFileDialog.getOpenFileName(self, "Open File", "", "iso files (*.zip)", options=options)
        self.ui.isoFile.setText(file_name)
        self.targetIso = file_name

    def selectTheDevice(self):
        self.targetDevice = self.ui.deviceNames.currentText()
        self.ui.start.setEnabled(True)

    def deviceDetect(self, *args):
        #while True:
        self.bus = dbus.SessionBus()
        obj = self.bus.get_object("org.gtk.vfs.UDisks2VolumeMonitor",
                             "/org/gtk/Private/RemoteVolumeMonitor")
        iface = dbus.Interface(obj, "org.gtk.Private.RemoteVolumeMonitor")
        self.ui.deviceNames.clear()
        for i in iface.List()[2]:
            print(i[5].replace("%20"," "))
            self.ui.deviceNames.addItem(r"/"+i[5].replace("%20"," ").lstrip(r"file:///"))
            print("-------------------------")

    def controlState(self):
        if not os.path.exists(self.targetIso):
            a = QDialog()
            Step1().setupUi(a)
            a.exec_()
            return
        if not os.path.exists(self.targetDevice):
            a = QDialog()
            Step2().setupUi(a)
            a.exec_()
            return
        self.page2()

window = main()

