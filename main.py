#!/usr/bin/python
#-*-encoding:utf-8-*-

import gi
gi.require_version("Gtk", '3.0')
gi.require_version("UDisks", "2.0")
from gi.repository import Gtk, UDisks, Gdk, GLib ,GObject
from threading import Thread, Lock, Event
from usbDetect import getAllUnixDevices
import os
import sys, signal

class process(Thread):
    def __init__(self, forProcess, forCancel, forKill, forFinish):
        self.running = True
        self.cancel = True
        self.kill = True
        self.finish = True
        self.isSuccess = None
        
        self.forProcess = forProcess
        self.forCancel = forCancel
        self.forKill = forKill
        self.forFinish = forFinish
        super().__init__()

    def run(self):
        print("yeniden başliom...")
        
        while self.running and self.cancel and self.kill and self.finish:
            self.forProcess.emit("process")
        
        if not self.cancel: #Event.isSet():
            GLib.idle_add(self.forCancel.emit,"cancel")

        if not self.kill:
            GLib.idle_add(self.forKill.emit, "kill")

        if not self.finish:
            GLib.idle_add(self.forFinish.emit, "finished", self.isSuccess)

        print("öldüm")        
            
            
class cancelSignal(GObject.GObject):
    def __init__(self):
        GObject.GObject.__init__(self)

GObject.type_register(cancelSignal)
GObject.signal_new("cancel", cancelSignal, GObject.SIGNAL_RUN_FIRST,GObject.TYPE_NONE, ())

class barSignal(GObject.GObject):
    def __init__(self):
        GObject.GObject.__init__(self)

GObject.type_register(barSignal)
GObject.signal_new("update", barSignal, GObject.SIGNAL_RUN_FIRST,GObject.TYPE_NONE, (float, float, float, ))

class finishSignal(GObject.GObject):
    def __init__(self):
        GObject.GObject.__init__(self)

GObject.type_register(finishSignal)
GObject.signal_new("finished", finishSignal, GObject.SIGNAL_RUN_FIRST,GObject.TYPE_NONE, (int,))

class processSignal(GObject.GObject):
    def __init__(self):
        GObject.GObject.__init__(self)

GObject.type_register(processSignal)
GObject.signal_new("process", processSignal, GObject.SIGNAL_RUN_FIRST,GObject.TYPE_NONE, ())

class killSignal(GObject.GObject):
    def __init__(self):
        GObject.GObject.__init__(self)

GObject.type_register(killSignal)
GObject.signal_new("kill", killSignal, GObject.SIGNAL_RUN_FIRST,GObject.TYPE_NONE, ())



class fux(Gtk.Builder):
    lock = Lock()
    def __init__(self):
        super().__init__()
        self.dev = ("", 0.0)
        self.selectedFile = ""
        self.selectedTarget = ""
        self.size = 0
        self.total_size = 0
        self.written = 0

        self.add_from_file("fux_image_writer.ui")
        self.window = self.get_object("window1")
        self.window.connect("destroy", self.close)
        self.window.set_title("FUX-USB KALIP YAZICI")

        self.content = self.get_object("resultText")

        self.devicelist = self.get_object("deviceCombo")
        self.devicelist.connect("changed", self.selectDevice)
        
        #signals
        self.updateBarSignal = barSignal()
        self.updateBarSignalId = self.updateBarSignal.connect("update", self.updateBar)
        self.finishProcessSignal = finishSignal()
        self.finishProcessId = self.finishProcessSignal.connect("finished", self.on_finished)
        self.myProcessSignal = processSignal()
        self.processId = self.myProcessSignal.connect("process", self.processManager)
        self.myCancelSignal = cancelSignal()
        self.cancelId = self.myCancelSignal.connect("cancel", self.on_cancel)
        self.killSignal = killSignal()
        self.killId = self.killSignal.connect("kill", self.on_close)

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
        filt.add_pattern("*.[iI][mM][gG]")
        filt.add_pattern("*.[iI][sS][oO]")
        self.chooser.set_filter(filt)
        self.chooser.connect("file-set", self.selectFile)
        self.udisksCli = UDisks.Client.new_sync()
        #list store
        self.devicemodel = Gtk.ListStore(str, str, str)
        #renderer
        renderer_text = Gtk.CellRendererText()
        self.devicelist.pack_start(renderer_text, True)
        self.devicelist.add_attribute(renderer_text, "text", 2)
        
        self.playButton = self.get_object("state")
        self.playButton.set_label("Başla")        
        self.playId = self.playButton.connect("clicked", self.control)
  
        self.cancelButton = self.get_object("cancel")
        self.cancelButton.connect("clicked", self.cancel)
        self.cancelButton.set_sensitive(False)    

        self.bar = self.get_object("processBar")
        self.bar.set_show_text(True)
        
        self.get_devices("")
        self.udisksCliListener = self.udisksCli.connect("changed", self.get_devices)
        self.window.show_all()

    def get_devices(self, widget):
        self.devicemodel.clear()  #for update
        result = getAllUnixDevices()
        for i in result:
            self.devicemodel.append([str(i[2]),i[1],i[0]+" "+i[1]])
        self.devicelist.set_model(self.devicemodel)

    def selectDevice(self, widget):
        iter_ = self.devicelist.get_active_iter()
        if iter_ is not None:
            print(self.devicemodel.get_value(iter_, 1),self.devicemodel.get_value(iter_, 0))
            self.dev = (self.devicemodel.get_value(iter_, 1),self.devicemodel.get_value(iter_, 0))
            #print(self.dev[0].lstrip("/dev/"))

    def selectFile(self, widget):
        self.selectedFile =  self.chooser.get_filename()

    def control(self, widget):
        if not os.path.exists(self.dev[0]):
            #you must select a device
            response = self.deviceWarnWin.run()
            if response is not None:
                self.deviceWarnWin.hide()
            return
            
        if not os.path.exists(self.selectedFile):
            #you must select a disk image file
            self.isoWarnWin.run()
            self.isoWarnWin.hide()
            return

        if float(self.dev[1]) < os.path.getsize(self.selectedFile):
            #you must get enough space
            self.spaceWarWin.run()
            self.spaceWarWin.hide()
            return

        self.startProcess()

    def updateBar(self, object, value, size, written):
        Gdk.threads_enter()
        #print("---UPDATEBAR----", value, size, written)
        self.bar.set_fraction(value)
        self.size = size
        self.written = written
        Gdk.threads_leave()

    

    def processManager(self, object):
        if self.isStop:
            return
        buffer_ = self.sourceFileHandler.read(1096)
        if len(buffer_) == 0:
            """process finished""" 
            self.isStop = True               
            self.targetFileHandler.close()
            self.sourceFileHandler.close()
            if self.size == self.total_size:
                """processs is finished successfully"""
                self.lock.acquire()
                self.processThread.isSuccess = 1
                self.processThread.finish = False
                self.lock.release()              
                return
            else:
                """processs is failed"""
                self.lock.acquire()
                self.processThread.isSuccess = 1
                self.processThread.finish = False
                self.lock.release()
                return
                   
        self.size += len(buffer_)
        self.written += self.size
        self.targetFileHandler.write(buffer_) 
        print(float(self.size / self.total_size))          
        if self.written >= self.total_size/100:
            try:
                self.targetFileHandler.flush()
                self.written = 0
            except ValueError:
                pass
        self.updateBarSignal.emit("update",float(self.size/self.total_size), self.size, self.written)
        
    def startProcess(self):
        self.isStop = False
        self.size = 0
        self.written = 0
        self.chooser.set_sensitive(False)
        self.devicelist.set_sensitive(False)
        self.cancelButton.set_sensitive(True)
        self.udisksCli.handler_block(self.udisksCliListener)
        self.playButton.handler_block(self.playId)
        self.playId = self.playButton.connect("clicked", self.pause)
        self.playButton.set_label("Durdur")

        self.sourceFileHandler = open(self.selectedFile, "rb")
        self.targetFileHandler = open(self.dev[0], "wb")
        self.total_size = os.path.getsize(self.selectedFile)
        self.content.get_buffer().set_text("%s , %s 'e yazılıyor..\n"%(self.selectedFile, self.dev[0]))
        self.processThread = process(self.myProcessSignal, self.myCancelSignal, self.killSignal, self.finishProcessSignal)
        #self.processThread.daemon = True
        self.processThread.start()

    def pause(self, widget):
        self.lock.acquire()
        self.processThread.running = False
        self.playButton.disconnect(self.playId)
        self.lock.release()
        self.lock = Lock()
        self.playButton.set_label("Devam Et")
        self.playId = self.playButton.connect("clicked", self.continue_)

    def continue_(self, widget):
        self.playButton.disconnect(self.playId)
        self.playButton.set_label("Durdur")
        self.playId = self.playButton.connect("clicked", self.pause)
        self.processThread = process(self.myProcessSignal, self.myCancelSignal, self.killSignal, self.finishProcessSignal)
        #self.processThread.daemon = True
        self.processThread.start()


    def cancel(self, widget):
        self.lock.acquire()
        if not self.processThread.running:
            self.on_cancel(None)
        else:
            self.processThread.cancel = False
        self.lock.release()
        self.lock = Lock()
        
        
    def on_cancel(self, object):
        self.sourceFileHandler.close()
        self.targetFileHandler.close()
        self.size = 0
        self.total_size = 0
        self.written = 0
        self.playButton.disconnect(self.playId)
        self.playId = self.playButton.connect("clicked",self.control)
        self.playButton.set_label("Başla")
        self.devicelist.set_sensitive(True)
        self.chooser.set_sensitive(True)
        self.cancelButton.set_sensitive(False)        
        self.bar.set_fraction(0.0)

    def on_finished(self, object, success_result):
        
        if success_result == 1:
            """mission successful"""
            text_buffer = self.content.get_buffer()
            end_iter = text_buffer.get_end_iter()
            text_buffer.insert(end_iter,"Kalıp başarıyla yazıldı.")
        else:
            """mission failed"""
            text_buffer = self.content.get_buffer()
            end_iter = text_buffer.get_end_iter()
            text_buffer.insert(end_iter,"Kalıp yazma başarısız")
        self.playButton.disconnect(self.playId)
        self.size = 0
        self.written = 0
        self.total_size = 0
        self.cancelButton.set_sensitive(False)
        self.playButton.set_label("Başla")
        self.playId = self.playButton.connect("clicked", self.control)
        self.devicelist.set_sensitive(True)
        self.chooser.set_sensitive(True)
        self.udisksCli.handler_unblock(self.udisksCliListener)
        self.bar.set_fraction(0.0)
        self.lock = Lock()

    def close(self, wid):
        self.lock = Lock()
        try:
            self.lock.acquire()
            self.processThread.kill = False
            self.lock.release()
        except:
            sys.exit(self.window.destroy())

    def on_close(self, object):
        self.sourceFileHandler.close()
        self.targetFileHandler.close()
        self.window.destroy()
        try:
            signal.pthread_kill(self.processThread.ident, signal.SIGTERM)
        except:
            sys.exit()
        Gdk.threads_leave()
        
        
         

GObject.threads_init()
Gdk.threads_init()
app = fux()
Gtk.main()
Gdk.threads_leave()

