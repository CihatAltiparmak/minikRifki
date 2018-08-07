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
        #FOR WRITE ISO FİLES
        self.source = ""
        self.dev = ""
        self.processStart = False
        self.play = False

        self.add_from_file("ilkGlade.ui")
        self.window = self.get_object("window1")
        self.window.connect("destroy", self.close)
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
        self.devicemodel = Gtk.ListStore(str, str)
        #renderer
        renderer_text = Gtk.CellRendererText()
        self.devicelist.pack_start(renderer_text, True)
        self.devicelist.add_attribute(renderer_text, "text", 1)
        
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
            self.devicemodel.append([i[1],i[0]+" "+i[1]])
        self.devicelist.set_model(self.devicemodel)
        

    def deviceSelected(self, widget):
        iter_ = self.devicelist.get_active_iter()
        if iter_ is not None:
            self.dev = self.devicemodel.get_value(iter_, 0)    
            print(self.dev)
        

    def fileSelected(self, widget):
        self.source =  self.chooser.get_filename()
        print(self.source)

    def formatDeviceSelected(self, widget):
        iter_ = self.formatlist.get_active_iter()
        if iter_ is not None:
            self.devFormat = self.formatmodel.get_value(iter_, 0)    
            print(self.devFormat)
        
    def formatOptionSelected(self, widget):
        iter_ = self.format_option_list.get_active_iter()
        if iter_ is not None:
            self.devOption = self.format_option_model.get_value(iter_, 0)    
            print(self.devOption)
        

    def control(self):
        if not os.path.exists(self.dev):
            #you must select a device
            self.deviceWarnWin.show_all()
            return
            
        if not os.path.exists(self.source):
            #you must select a disk image file
            self.isoWarnWin.show_all()
            return

        
        self.writeImage("",file_=self.source, target=self.dev)

    
    def updateBar(self, data):
        self.bar.set_fraction(data)

    

    def writeImage(self, wid, file_=None, target=None):
        #alan uygunmu diye olc
        #alan uygun degilse self.spaceErr.show_all(); return
        self.content.get_buffer().set_text("Writing %s to %s \n"%(file_, target))
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
        os.kill(os.getpid(), SIGTERM) #FIXME How can i finished this process better ?I think, his is bad wall.But when i used exit() func, program is not answering. 
       

    def continue_(self, widget):
        try:
            self.t.continue_()
            self.playButton.set_label("Durdur")
            self.playButton.disconnect_by_func(self.continue_)
            self.id = self.playButton.connect("clicked", self.pause)
        except:
            self.t.cancel()
            self.unknownErr.show_all()

    def pause(self, widget):
        try:
            self.t.pause()
            self.playButton.set_label("Devam Et")
            self.playButton.disconnect_by_func(self.pause)
            self.id = self.playButton.connect("clicked", self.continue_)
        except:
            self.unknownErr.show_all()

    def __cancel__(self):
        try:
            self.t.cancel()
            self.bar.set_fraction(0.0)            
            self.playButton.disconnect(self.id) 
            self.playButton.connect("clicked",self.fired)
            self.playButton.set_label("Başla")
            self.cancelButton.set_sensitive(False)
        
        except:
            exit() #log tutulmali

    def finished(self):
        try:
            self.bar.set_fraction(0.0)            
            self.playButton.disconnect(self.id) 
            self.playButton.connect("clicked",self.fired)
            self.playButton.set_label("Başla")
            self.cancelButton.set_sensitive(False)
        
        except:
            exit() #log tutulmali

GObject.threads_init()
Gdk.threads_init()
Gdk.threads_enter()
app = rifki()
Gtk.main()
Gdk.threads_leave()
