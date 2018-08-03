import gi
gi.require_version("Gtk", '3.0')
gi.require_version("UDisks", "2.0")
from gi.repository import Gtk, UDisks
import dbus
from usbDetect import getAllUnixDevices
from raw_format import format
from functools import partial
import sys
sys.path.append("./rifkiFux")
import os


class rifki(Gtk.Builder):
    def __init__(self):        
        super().__init__()
        self.source = None
        self.dev = None
        self.processStart = False
        self.play = False

        self.add_from_file("ilkGlade.ui")
        self.window = self.get_object("window1")
        self.window.connect("destroy", self.close)

        self.devicelist = self.get_object("deviceCombo")
        self.devicelist.connect("changed", self.deviceSelected)

        self.chooser = self.get_object("selectedFile")
        filt = Gtk.FileFilter()
        filt.add_pattern("*.zip")
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
        for i in dir(self.playButton):
            print(i)
        #help(self.playButton)
        self.fired = lambda x: self.writeImage(wid="",file_=self.source, target=self.dev)
        self.playButton.connect("clicked", self.fired)  
        self.cancelButton = self.get_object("cancel")
        self.cancelButton.connect("clicked", lambda x: self.__cancel__())

        self.bar = self.get_object("processBar")

        self.get_devices()
        self.udisksCliListener = self.udisksCli.connect("changed", lambda x: self.get_devices())
        self.window.show_all()

    def get_devices(self):
        self.devicemodel.clear()  #for update
        result = getAllUnixDevices()
        for i in result:
            print(i)
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
    def control(self):
        if not os.path.exists(self.dev):
            #you must select a device
            pass
        if not os.path.exists(self.chooser.get_filename()):
            #you must select a disk image file
            pass

        #unmount device solved
        #format usb device solved
        format("/org/freedesktop/UDisks2/block_devices/"+self.dev.lstrip("/dev/"))
        #write disk image

    def format(self):
        pass
    
    def updateBar(self, data):
        self.bar.set_fraction(data)

    def writeImage(self, wid, file_=None, target=None):
        #alan uygunmu diye olc
        while True:
            if not self.processStart:
                self.playButton.disconnect_by_func(self.fired)
                #self.playButton.set_label("Duraklat")
                #self.playButton.connect("clicked", self.pause)
                self.bar.set_fraction(0.0)
                self.input = open(file_, "rb")
                self.output = open(target, "wb")
                self.processStart = True
                self.play = True
                self.total_size = os.path.getsize(file_)
                self.increment = self.total_size / 100
                self.size = 0
                self.written = 0
   
            self.buffer = self.input.read(1096)
            
            if len(self.buffer) == 0:
            #"""process finished"""
                print("finished")
                self.output.flush()
                self.input.close()
                self.output.close()            
                self.play = False
                self.processStart= False
                """
                try:
                    self.playButton.disconnect_by_func(self.continue_)
                except:
                    self.playButton.disconnect_by_func(self.pause) #FIXME i do not know 
                """
                return
                
            self.output.write(self.buffer)
            self.size += len(self.buffer)
            print(float(self.size/self.total_size))
            self.written += len(self.buffer)
            self.updateBar(float(self.size/self.total_size))
            if self.written >= self.increment:
                self.output.flush()
                self.written = 0
            """
            if not self.play:
                break#self.writeImage(wid="")
            """
            

        #except RecursionError:
            #self.writeImage(wid = "")
            #print("recursion")

    def close(self, *args):
        exit()
    """
    def pause(self, *args):
        self.playButton.disconnect_by_func(self.pause)
        self.play = False
        self.playButton.set_label("Devam Et")
        self.playButton.connect("clicked", self.continue_)

    def continue_(self, *args):
        self.playButton.disconnect_by_func(self.continue_)
        self.play = True
        self.playButton.set_label("Duraklat")
        self.playButton.connect("clicked", self.pause)
        self.writeImage(wid="")
    """   
    def __exit__(self):
        pass
    def __cancel__(self):
        with self.processStart as f:
            f = False
            self.play = False
        #self.processStart = False
            self.input.close()
            self.output.close()
app = rifki()
Gtk.main()
