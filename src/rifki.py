import gi
gi.require_version("Gtk", '3.0')
gi.require_version("UDisks", "2.0")
from gi.repository import Gtk, UDisks,  GObject, Gdk, GLib
import dbus

from usbDetect import getAllUnixDevices
from raw_write import writeProcess
from notifications import *

from queue import Queue
from functools import partial
import sys
sys.path.append("./rifkiFux")
import os
from signal import *



class rifki(Gtk.Builder):
    def __init__(self):        
        super().__init__()
        #FOR WRITE ISO FILES
        self.source = ""
        self.dev = ("",0)
        self.processStart = False
        self.play = False

        self.add_from_file("fux_image_writer.ui")
        self.window = self.get_object("window1")
        self.window.connect("destroy", self.close)
        self.window.set_title("FUX-USB KALIP YAZICI")

        self.content = self.get_object("resultText")

        self.devicelist = self.get_object("deviceCombo")
        self.devicelist.connect("changed", self.deviceSelected)
        
        #warnings
        self.isoWarnWin = self.get_object("fileWarning")
        self.deviceWarnWin = self.get_object("deviceWarning")

        #errors
        self.unknownErr = self.get_object("unknownError")
        self.spaceErr = self.get_object("spaceError")
        self.downloadErr = self.get_object("downloadError")

        #informations
        self.formatInfo = self.get_object("formatInfo")
        
        self.chooser = self.get_object("selectedFile")
        filt = Gtk.FileFilter()
        filt.add_pattern("*.iso")
        self.chooser.set_filter(filt)
        self.chooser.connect("file-set", self.fileSelected)
        self.udisksCli = UDisks.Client.new_sync()
        #list store
        self.devicemodel = Gtk.ListStore(str, str, str)
        #renderer
        renderer_text = Gtk.CellRendererText()
        self.devicelist.pack_start(renderer_text, True)
        self.devicelist.add_attribute(renderer_text, "text", 2)
        
        self.playButton = self.get_object("state")
        self.playButton.set_label("Başla")
        
        self.fired = lambda x: self.control()
        self.playButton.connect("clicked", self.fired)  
        self.cancelButton = self.get_object("cancel")
        self.cancelButton.connect("clicked", lambda x: self.__cancel__())
        self.cancelButton.set_sensitive(False)    

        self.bar = self.get_object("processBar")
        self.bar.set_show_text(True)
        
        self.get_devices()
        self.udisksCliListener = self.udisksCli.connect("changed", lambda x: self.get_devices())
        self.window.show_all()

    def get_devices(self):
        self.devicemodel.clear()  #for update
        result = getAllUnixDevices()
        for i in result:
            self.devicemodel.append([str(i[2]),i[1],i[0]+" "+i[1]])
        self.devicelist.set_model(self.devicemodel)
        

    def deviceSelected(self, widget):
        iter_ = self.devicelist.get_active_iter()
        if iter_ is not None:
            self.dev = (self.devicemodel.get_value(iter_, 1),self.devicemodel.get_value(iter_, 0)) 
        

    def fileSelected(self, widget):
        self.source =  self.chooser.get_filename()
        

    def control(self):
        if not os.path.exists(self.dev[0]):
            #you must select a device
            response = self.deviceWarnWin.run()
            if response is not None:
                self.deviceWarnWin.hide()
            return
            
        if not os.path.exists(self.source):
            #you must select a disk image file
            self.isoWarnWin.run()
            self.isoWarnWin.hide()
            return

        if float(self.dev[1]) < os.path.getsize(self.source):
            #you must get enough space
            self.spaceWarWin.run()
            self.spaceWarWin.hide()
            return

        
        self.writeImage("",file_=self.source, target=self.dev[0])

    
    def updateBar(self, data):
        self.bar.set_fraction(data)

    

    def writeImage(self, wid, file_=None, target=None):
        self.devicelist.set_sensitive(False)
        self.chooser.set_sensitive(False)
        self.content.get_buffer().set_text("%s , %s 'e yazılıyor..\n"%(file_, target))
        self.playButton.disconnect_by_func(self.fired)
        self.id = self.playButton.connect("clicked", self.pause)
        self.playButton.set_label("Durdur")
        self.cancelButton.set_sensitive(True)

       
        a = Queue()
        for i in [False, file_, target, "", "", "", "", "", self.finished]:
            a.put(i)
        self.t = writeProcess(a, self.bar, self.content)
        self.t.start()        
        

    def close(self, w):        
        os.kill(os.getpid(), SIGTERM) #FIXME How can i finished this process better ?I think, it is bad wall.But when i used exit() func, program is not answering. 
       

    def continue_(self, widget):
        try:
            self.t.continue_()
            self.playButton.set_label("Durdur")
            self.playButton.disconnect_by_func(self.continue_)
            self.id = self.playButton.connect("clicked", self.pause)
        except:
            self.t.cancel()
            self.unknownErr.run()
            self.unknownErr.hide()

    def pause(self, widget):
        try:
            self.t.pause()
            #Gdk.threads_leave()
            self.playButton.set_label("Devam Et")
            self.playButton.disconnect_by_func(self.pause)
            self.id = self.playButton.connect("clicked", self.continue_)
        except:
            self.unknownErr.run()
            self.unknownErr.hide()

    def __cancel__(self):
        try:
            
            self.t.pause()
            self.t.cancel()
            Gdk.threads_leave()
            self.bar.set_fraction(0.0)            
            self.playButton.disconnect(self.id) 
            self.playButton.connect("clicked",self.fired)
            self.playButton.set_label("Başla")
            self.cancelButton.set_sensitive(False)
            self.devicelist.set_sensitive(True)
            self.chooser.set_sensitive(True)
        
        except:
            exit() #log tutulmali

    def finished(self):
        try:
            self.bar.set_fraction(0.0)            
            self.playButton.disconnect(self.id) 
            self.playButton.connect("clicked",self.fired)
            self.playButton.set_label("Başla")
            self.cancelButton.set_sensitive(False)

            self.devicelist.set_sensitive(True)
            self.chooser.set_sensitive(True)
        
        except:
            exit() #log tutulmali

GObject.threads_init()
Gdk.threads_init()
Gdk.threads_enter()
app = rifki()
Gtk.main()
Gdk.threads_leave()
