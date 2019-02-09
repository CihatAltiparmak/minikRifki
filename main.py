#!/usr/bin/python3

#
# author => Cihat Altiparmak jarbay910@gmail.com
#

import gi
gi.require_version("Gtk", '3.0')
gi.require_version("UDisks", "2.0")

from gi.repository import Gtk, UDisks, Gdk, GLib ,GObject

from threading import Thread, Lock, Event, activeCount

import time
import os
import sys
import argparse


class Dialogs(Gtk.Dialog):
    def __init__(self, content, parent):
        Gtk.Dialog.__init__(self, "milisDialog", parent, 0,
                         (Gtk.STOCK_OK, Gtk.ResponseType.OK))
        self.set_default_size(400, 500)
        label = Gtk.Label(content)
        box = self.get_content_area()
        box.add(label)
        self.show_all()

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

class writeThread(Thread):
    def __init__(self, written,
                       total_size,
                       size,
                       targetDeviceHandler,
                       sourceFileHandler,
                       updatePosterSignal, finishProcessSignal, window):
        self.written = written
        self.total_size = total_size
        self.size = size
        self.targetDeviceHandler = targetDeviceHandler
        self.sourceFileHandler = sourceFileHandler
        self.updatePosterSignal = updatePosterSignal
        self.finishProcessSignal = finishProcessSignal
        self.window = window
        self.permission = True
        self.running = True
        self.killing = False

        self.lock = Lock()
        self.cancel_event = Event()
        self.state_event = Event()

        super(writeThread, self).__init__()
        self.setDaemon(True) #  when main thread died, this thread must die

    def run(self):
        print('[32m'+"[ WriteThread ] -> is started"+'[0m')
        try:
            while not self.cancel_event.isSet():
                if not self.state_event.isSet():
                    self.write()
            self.updatePosterSignal.emit("update",0.0, 0.0, 0.0)
        except:
            unknownErr = Dialogs("Unknown Error", self.window)
            response = unknownErr.run()
            if response == Gtk.ResponseType.OK:
                unknownErr.destroy()
        finally:
            self.sourceFileHandler.close()
            self.targetDeviceHandler.close()
                
        print('[32m'+"[ WriteThread ] -> is closed"+'[0m')

    def write(self):
        buffer_ = self.sourceFileHandler.read(1096)
        if len(buffer_) == 0:
            """process finished"""
            if self.size == self.total_size:
                """processs is finished successfully"""
                self.cancel_event.set()
                self.isSuccess = 1
                print("process is finished successfully")
            else:
                """processs is failed"""
                self.cancel_event.set()
                self.isSuccess = 0
                print("process is failed")
            self.finishProcessSignal.emit("finished", self.isSuccess)
        else:  
            self.size += len(buffer_)
            self.written += self.size
            self.targetDeviceHandler.write(buffer_)          
            if self.written >= self.total_size/100:
                self.targetDeviceHandler.flush()
                self.written = 0
            self.updatePosterSignal.emit("update",float(self.size/self.total_size), self.size, self.written)

    def cancel(self):
        self.pause()
        self.cancel_event.set()

    def pause(self):
        self.state_event.set()

    def continue_(self):
        self.state_event.clear()
           

class milisImageWriter(Gtk.Builder):
    def __init__(self, iso_path=None):
        super(milisImageWriter, self).__init__()
        self.selectedFile = ""
        self.selectedTarget = ""
        self.size = 0
        self.total_size = 0
        self.written = 0
        self.write_thread = None
        self.targetDeviceHandler = None
        self.sourceFileHandler = None

        self.add_from_file("milis_image_writer.ui")
        self.window = self.get_object("window1")
        self.window.connect("destroy", self.close)
        self.window.set_title("MİLİS-USB KALIP YAZICI")

        self.content = self.get_object("resultText")

        self.devicelist = self.get_object("deviceCombo")
        self.devicelist.connect("changed", self.selectDevice)

        
        # signals
        self.updateBarSignal = barSignal()
        self.updateBarSignalId = self.updateBarSignal.connect("update", self.updateBar)
        self.finishProcessSignal = finishSignal()
        self.finishProcessId = self.finishProcessSignal.connect("finished", self.on_finished)
        
        self.chooser = self.get_object("selectedFile")
        filt = Gtk.FileFilter()
        filt.add_pattern("*.[iI][mM][gG]")
        filt.add_pattern("*.[iI][sS][oO]")
        self.chooser.set_filter(filt)
        self.chooser.connect("file-set", self.selectFile)
        self.udisksCli = UDisks.Client.new_sync()

        # list store
        self.devicemodel = Gtk.ListStore(str, str, float)

        # renderer

        renderer_text = Gtk.CellRendererText()
        self.devicelist.pack_start(renderer_text, True)
        self.devicelist.add_attribute(renderer_text, "text", 1)
        
        self.playButton = self.get_object("state")
        self.playButton.set_label("yazdır")        
        self.playId = self.playButton.connect("clicked", self.control)
  
        self.cancelButton = self.get_object("cancel")
        self.cancelButton.connect("clicked", self.cancel)
        self.cancelButton.set_sensitive(False)    

        self.bar = self.get_object("processBar")
        self.bar.set_show_text(True)
        
        self.get_devices()
        self.udisksCliListener = self.udisksCli.connect("changed", self.get_devices)

        if iso_path is not None:
            if os.path.exists(iso_path):
                self.chooser.set_filename(iso_path)
                self.selectFile(self.chooser)
        self.window.show_all()

    def get_devices(self, widget=None):
        self.devicemodel.clear()
        dct = []
        self.dev = None

        manager = self.udisksCli.get_object_manager()

        for obj in manager.get_objects():
            if obj is not None:
                block = obj.get_block()
                if block is not None:
                    drive = self.udisksCli.get_drive_for_block(block)
                    if drive is not None:
                        is_usb = str(drive.get_property("connection-bus")) == 'usb'
                        real_size = int(drive.get_property('size'))
                        optical = bool(drive.get_property('optical'))
                        removable = bool(drive.get_property('removable'))

                        if is_usb and real_size > 0 and removable and not optical:
                            name = "unknown"

                            block = obj.get_block()
                            if block is not None:
                                name = block.get_property('device')
                                name = ''.join([i for i in name if not i.isdigit()])

                            driveVendor = str(drive.get_property('vendor'))
                            driveModel = str(drive.get_property('model'))

                            if driveVendor.strip() != "":
                                driveModel = "%s %s" % (driveVendor, driveModel)

                            if real_size >= 1000000000000:
                                size = "%.0fTB" % round(real_size / 1000000000000)
                            elif real_size >= 1000000000:
                                size = "%.0fGB" % round(real_size / 1000000000)
                            elif real_size >= 1000000:
                                size = "%.0fMB" % round(real_size / 1000000)
                            elif real_size >= 1000:
                                size = "%.0fkB" % round(real_size / 1000)
                            else:
                                size = "%.0fB" % round(real_size)

                            item = "%s (%s) - %s" % (driveModel, name, size)

                            if item not in dct:
                                dct.append(item)
                                self.devicemodel.append([str(name), str(item), real_size])

        self.devicelist.set_model(self.devicemodel)

    def selectDevice(self, widget):
        iter_ = self.devicelist.get_active_iter()
        if iter_ is not None:
            self.dev = (self.devicemodel.get_value(iter_, 0), self.devicemodel.get_value(iter_, 2))
            print("func selectDevice : ", self.dev, "activeThread: ", activeCount())
            self.selectedTarget = self.dev[0]

    def selectFile(self, widget):
        self.selectedFile =  self.chooser.get_filename()

    def updateBar(self, object, value, size, written):
        Gdk.threads_enter()
        # print("---UPDATEBAR----", value, size, written)
        self.bar.set_fraction(value)
        self.size = size
        self.written = written
        Gdk.threads_leave()

    def control(self, widget):
        if self.dev is None or not os.path.exists(self.dev[0]):
            # you must select a device
            deviceWarnWin = Dialogs("bir aygıt seçmelisiniz", self.window)
            response = deviceWarnWin.run()
            if response == Gtk.ResponseType.OK:
                deviceWarnWin.destroy()
            return
            
        if not os.path.exists(self.selectedFile):
            # you must select a disk image file
            isoWarnWin = Dialogs("bir disk kalıbı dosyası seçmelisiniz", self.window)
            response = isoWarnWin.run()
            if response == Gtk.ResponseType.OK:
                isoWarnWin.hide()
           
            return

        if float(self.dev[1]) < os.path.getsize(self.selectedFile):
            # you must get enough space
            spaceWarWin = Dialogs("you must get enough space", self.window)
            response = spaceWarWin.run()
            if response == Gtk.ResponseType.OK: 
                self.spaceWarWin.hide()
            return

        self.file_closing()
        if activeCount() >= 2:
            print("[ Thread Danger ]")


        self.chooser.set_sensitive(False)
        self.devicelist.set_sensitive(False)
        self.cancelButton.set_sensitive(True)
        self.udisksCli.handler_block(self.udisksCliListener)

        
        self.playButton.disconnect(self.playId)
        self.playId = self.playButton.connect("clicked", self.pause)
        self.playButton.set_label("duraklat")

        self.content.get_buffer().set_text("%s , %s 'e yaziliyor..\n"%(self.selectedFile, self.dev[0]))

        self.sourceFileHandler = open(self.selectedFile, "rb")
        self.targetDeviceHandler = open(self.selectedTarget, "wb")
        self.total_size = os.path.getsize(self.selectedFile)
        self.write_thread = writeThread(self.written,
                                        self.total_size,
                                        self.size,
                                        self.targetDeviceHandler, 
                                        self.sourceFileHandler,
                                        self.updateBarSignal,
                                        self.finishProcessSignal,
                                        self.window)
        self.write_thread.start()
        print("started: ", activeCount())

    def pause(self, obj):
        self.write_thread.pause()
        print("waiting", self.write_thread.isAlive(), "activeThread: ", activeCount())
        self.playButton.disconnect(self.playId)
        self.playButton.set_label("devam et")
        self.playId = self.playButton.connect("clicked", self.continue_)

    def continue_(self, obj):
        print("not waiting", self.write_thread.isAlive(), "activeThread", activeCount())
        self.playButton.disconnect(self.playId)
        self.playButton.set_label("durdur")
        self.playId = self.playButton.connect("clicked", self.pause)
        self.write_thread.continue_()

    def cancel(self, obj):
        self.write_thread.cancel()
        time.sleep(0.1)
        print("[ Is thread death ] = ", self.write_thread.isAlive())
        self.size = 0
        self.total_size = 0
        self.written = 0
        self.selectedFile = ""
        self.selectedTarget = ""
        self.playButton.disconnect(self.playId)
        self.playId = self.playButton.connect("clicked",self.control)
        self.playButton.set_label("yazdır")
        self.devicemodel.clear()
        self.get_devices()
        self.devicelist.set_sensitive(True)
        self.chooser.unselect_all()
        self.chooser.set_sensitive(True)
        self.cancelButton.set_sensitive(False)        
        self.bar.set_fraction(0.0)
        self.file_closing()

    def on_finished(self, obj, success_result):
        self.sourceFileHandler.close()
        self.targetDeviceHandler.close()
        if success_result == 1:
            """mission successful"""
            text_buffer = self.content.get_buffer()
            end_iter = text_buffer.get_end_iter()
            text_buffer.insert(end_iter,"Kalip basariyla yazildi.")
        else:
            """mission failed"""
            text_buffer = self.content.get_buffer()
            end_iter = text_buffer.get_end_iter()
            text_buffer.insert(end_iter,"Kalip yazma basarisiz")
        self.playButton.disconnect(self.playId)
        self.size = 0
        self.written = 0
        self.total_size = 0
        self.cancelButton.set_sensitive(False)
        self.playButton.set_label("yazdır")
        self.playId = self.playButton.connect("clicked", self.control)
        self.devicelist.set_sensitive(True)
        self.chooser.set_sensitive(True)
        self.udisksCli.handler_unblock(self.udisksCliListener)
        self.bar.set_fraction(0.0)

    def close(self, object):
        try:
            if self.write_thread is not None:
                self.write_thread.cancel()
            self.file_closing()
        except:
            pass
        finally:
            Gtk.main_quit()

    def file_closing(self):
        if (self.targetDeviceHandler is not None) and  (not self.targetDeviceHandler.closed):
            self.targetDeviceHandler.close()
        if (self.sourceFileHandler is not None) and (not self.sourceFileHandler.closed):        
            self.sourceFileHandler.close()

def main(): 
    parser = argparse.ArgumentParser(description='milisImageWriter (milisImageWriter) <jarbay910@gmail.com>')
    parser.add_argument('-i', '--iso_path', dest='iso_path', help='Select the iso', type=str)  
    args = parser.parse_args()
    GObject.threads_init()
    Gdk.threads_init()
    if args.iso_path is not None:
        app = milisImageWriter(args.iso_path)
    else:       
        app = milisImageWriter()
    Gtk.main()
    Gdk.threads_leave()


if __name__ == "__main__":
    main()
