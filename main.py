#!/usr/bin/env python3
#-*-encoding:utf-8-*-

#
# author => Cihat Altiparmak jarbay910@gmail.com
#

import gi
gi.require_version("Gtk", '3.0')
gi.require_version("UDisks", "2.0")
gi.require_version('XApp', '1.0')

from gi.repository import Gtk, UDisks, Gdk, GLib ,GObject, XApp

import threading
from threading import Thread , Lock, activeCount
import multiprocessing
from multiprocessing import Process
import multiprocessing.sharedctypes

import time
import os
import sys
import argparse
import locale
import gettext
import signal
import syslog
import subprocess
# import parted


# https://technet.microsoft.com/en-us/library/bb490925.aspx
FORBIDDEN_CHARS = ["*", "?", "/", "\\", "|", ".", ",", ";", ":", "+", "=", "[", "]", "<", ">", "\""]

APP = 'mintstick'
LOCALE_DIR = "/usr/share/linuxmint/locale"
locale.bindtextdomain(APP, LOCALE_DIR)
gettext.bindtextdomain(APP, LOCALE_DIR)
gettext.textdomain(APP)
_ = gettext.gettext

PROCESS_PERCENT = multiprocessing.sharedctypes.Value('d', 0.0)
PROCESS_WRITTEN = multiprocessing.sharedctypes.Value('d', 0.0)
PROCESS_SIZE = multiprocessing.sharedctypes.Value('d', 0.0)


class Dialogs(Gtk.Dialog):
    def __init__(self, content, parent):
        Gtk.Dialog.__init__(self, "milisDialog", parent, 0,
                         (Gtk.STOCK_OK, Gtk.ResponseType.OK))
        self.set_default_size(200, 100)
        label = Gtk.Label(content)
        box = self.get_content_area()
        box.add(label)
        self.show_all()

class barSignal(GObject.GObject):
    def __init__(self):
        GObject.GObject.__init__(self)

GObject.type_register(barSignal)
GObject.signal_new("update", barSignal, GObject.SIGNAL_RUN_FIRST,GObject.TYPE_NONE, (float, float, float, ))

class cancelSignal(GObject.GObject):
    def __init__(self):
        GObject.GObject.__init__(self)

GObject.type_register(cancelSignal)
GObject.signal_new("cancel", cancelSignal, GObject.SIGNAL_RUN_FIRST,GObject.TYPE_NONE, (bool,))

class finishSignal(GObject.GObject):
    def __init__(self):
        GObject.GObject.__init__(self)

GObject.type_register(finishSignal)
GObject.signal_new("finished", finishSignal, GObject.SIGNAL_RUN_FIRST,GObject.TYPE_NONE, (int,))

class checkJobThread(Thread):
    def __init__(self, process, finish_signal):
        self.kill = threading.Event()
        self.process = process
        self.finish_signal = finish_signal
        super(checkJobThread, self).__init__()
        self.setDaemon(True)

    def run(self):
        print("checkJobThread is started")
        while not self.kill.is_set():
            if self.process.exitcode is not None:
                print("check_job_thread: process_exitcode => ", self.process.exitcode)
                self.finish_signal.emit("finished", self.process.exitcode)
                break
        print("checkJobThread is closed")

    def close_the_thread(self):
        self.kill.set()

class updateBarThread(Thread):
    def __init__(self, bar_signal, mode="iso", bar=None):
        self.bar_signal = bar_signal
        self.mode = mode
        self.kill = threading.Event()
        super(updateBarThread, self).__init__()
        self.setDaemon(True)
        if self.mode == "format":
            assert bar is not None
            self.bar = bar

    def run(self):
        print("updateBarThread is started")
        if self.mode == "iso":
            while not self.kill.is_set():
                self.bar_signal.emit("update", PROCESS_PERCENT.value, PROCESS_SIZE.value, PROCESS_WRITTEN.value)
                time.sleep(0.1)
            self.bar_signal.emit("update", 0.0, 0.0, 0.0)
        elif self.mode == "format":
            while not self.kill.is_set():
                self.bar.pulse()
                time.sleep(0.1)
            self.bar.set_fraction(0.0)
        print("updateBarThread is closed")
        
    def close_the_thread(self):
        self.kill.set()

class formatProcess(Process):
    def __init__(self, device_path, 
                       fstype, 
                       volume_label, 
                       uid, 
                       gid):
        
        self.device_path = device_path
        self.fstype = fstype
        self.volume_label = volume_label
        self.uid = uid
        self.gid = gid
        super(formatProcess, self).__init__()

    def run(self):
        # do_umount(device_path)

        partition_path = "%s1" % self.device_path
        if self.fstype == "fat32":
            partition_type = "fat32"
        if self.fstype == "ntfs":
            partition_type = "ntfs"
        elif self.fstype == "ext4":
            partition_type = "ext4"

        # First erase MBR and partition table , if any
        self.execute(["dd", "if=/dev/zero", "of=%s" % self.device_path, "bs=512", "count=1"])

        # Make the partition table
        self.execute(["parted", self.device_path, "mktable", "msdos"])

        # Make a partition (primary, with FS ID ext3, starting at 1MB & using 100% of space).
        # If it starts at 0% or 0MB, it's not aligned to MB's and complains
        self.execute(["parted", self.device_path, "mkpart", "primary", partition_type, "1", "100%"])

        # Call wipefs on the new partitions to avoid problems with old filesystem signatures
        self.execute(["wipefs", "-a", partition_path, "--force"])

        # Format the FS on the partition
        if self.fstype == "fat32":
            self.execute(["mkdosfs", "-F", "32", "-n", self.volume_label, partition_path])
        if self.fstype == "ntfs":
            self.execute(["mkntfs", "-f", "-L", self.volume_label, partition_path])
        elif self.fstype == "ext4":
            self.execute(["mkfs.ext4", "-E", "root_owner=%s:%s" % (self.uid, self.gid), "-L", self.volume_label, partition_path])

        # Exit
        exit(1)

    def execute(self, command):
        syslog.syslog(str(command))
        subprocess.call(command)
        subprocess.call(["sync"])

class writeProcess(Process):
    def __init__(self, written,
                       total_size,
                       size,
                       targetDeviceHandler,
                       sourceFileHandler,
                       updatePosterSignal, 
                       finishProcessSignal,
                       cancelProcessSignal, 
                       window, 
                       button):

        self.written = written
        self.total_size = total_size
        self.size = size

        self.targetDeviceHandler = targetDeviceHandler
        self.sourceFileHandler = sourceFileHandler

        self.updatePosterSignal = updatePosterSignal
        self.finishProcessSignal = finishProcessSignal
        self.cancelProcessSignal = cancelProcessSignal        
            
        self.window = window
        self.button = button
        self.permission = True
        self.running = True
        self.killing = False

        self.lock = Lock()
        self.cancel_event = multiprocessing.Event()
        self.state_event = multiprocessing.Event()

        super(writeProcess, self).__init__()
        self.daemon = True #  when main process died, other process must die as well

    def run(self):
        print('[32m'+"[ WriteThread ] -> is started"+'[0m')
        while not self.cancel_event.is_set():
            if not self.state_event.is_set():
                #try:
                self.write()
                # except:
                    # print("UnknownError")
                    # exit()
                    # self.cancelProcessSignal.emit("cancel", True)
                    # self.cancel_event.set()
                    
        self.updatePosterSignal.emit("update",0.0, 0.0, 0.0)
        self.button.set_sensitive(True)
        print('[32m'+"[ WriteThread ] -> is closed"+'[0m')

    def write(self):
        buffer_ = self.sourceFileHandler.read(2096)
        if len(buffer_) == 0:
            """process finished"""
            if self.size == self.total_size:
                """processs is finished successfully"""
                self.cancel_event.set()
                self.isSuccess = 0
                print("process is finished successfully")
            else:
                """processs is failed"""
                self.cancel_event.set()
                self.isSuccess = 4
                print("process is failed")
            exit(self.isSuccess)
        else:  
            self.size += len(buffer_)
            self.written += self.size
            self.targetDeviceHandler.write(buffer_)          
            if self.written >= self.total_size/100:
                self.targetDeviceHandler.flush()
                self.written = 0
            PROCESS_PERCENT.value = float(self.size/self.total_size)
            PROCESS_SIZE.value = float(self.size)
            PROCESS_WRITTEN.value = float(self.written)

    def cancel(self):
        self.pause()
        self.button.set_sensitive(False)
        self.cancel_event.set()

    def pause(self):
        self.state_event.set()

    def continue_(self):
        self.state_event.clear()
           

class milisImageWriter(Gtk.Builder):
    def __init__(self, mode, iso_path=None, filesystem=None):
        super(milisImageWriter, self).__init__()
        self.add_from_file("milis_image_writer.ui")
        self.selectedTarget = ""        
        self.targetDeviceHandler = None        
        self.mode = mode

        self.udisksCli = UDisks.Client.new_sync()
        self.udisksCliListener = self.udisksCli.connect("changed", self.get_devices)

        # signals
        self.updateBarSignal = barSignal()
        self.finishProcessSignal = finishSignal()
        self.cancelProcessSignal = cancelSignal()

        if mode == "iso":
            self.selectedFile = ""
            self.size = 0
            self.total_size = 0
            self.written = 0
            self.write_thread = None
            self.sourceFileHandler = None

            self.add_from_file("milis_image_writer.ui")
            self.window = self.get_object("iso_window")
            self.window.set_title(_("MİLİS-USB KALIP YAZICI"))

            self.content = self.get_object("resultText")

            self.devicelist = self.get_object("deviceCombo")
            self.devicelist.connect("changed", self.selectDevice)

        
            # signal connections for the write process
            self.updateBarSignalId = self.updateBarSignal.connect("update", self.updateBar) # to update progress bar
            self.finishProcessId = self.finishProcessSignal.connect("finished", self.on_write_finished) # on finish img writing process
            self.cancelProcessId = self.cancelProcessSignal.connect("cancel", self.cancel_the_write_process) # for unknown problems while writing device
        
            self.chooser = self.get_object("selectedFile")
            filt = Gtk.FileFilter()
            filt.add_pattern("*.[iI][mM][gG]")
            filt.add_pattern("*.[iI][sS][oO]")
            self.chooser.set_filter(filt)
            self.chooser.connect("file-set", self.selectFile)
            

            # list store
            self.devicemodel = Gtk.ListStore(str, str)

            # renderer

            renderer_text = Gtk.CellRendererText()
            self.devicelist.pack_start(renderer_text, True)
            self.devicelist.add_attribute(renderer_text, "text", 1)
        
            self.playButton = self.get_object("state")
            self.playButton.set_label(("başla"))        
            self.playId = self.playButton.connect("clicked", self.start_to_write)
  
            self.cancelButton = self.get_object("cancel")
            self.cancelButton.connect("clicked", self.cancel_the_write_process)
            self.cancelButton.set_sensitive(False)    

            self.bar = self.get_object("processBar")
            self.bar.set_show_text(True)
        
            # self.get_devices()

            if iso_path is not None:
                if os.path.exists(iso_path):
                    self.chooser.set_filename(iso_path)
                    self.selectFile(self.chooser)
            

        if mode == "format":
            self.window = self.get_object("format_window")
            
            self.progressbar = self.get_object("formatBar")
            self.filesystemlist = self.get_object("filesystem_combobox")
            self.filesystemlist.connect("changed", self.filesystem_selected)
            self.devicelist = self.get_object("formatCombo")
            self.devicelist.connect("changed", self.selectDevice)

            # signal connections for the write process
            # self.updateBarSignalId = self.updateBarSignal.connect("update", self.updateBar) # to update progress bar
            self.finishProcessId = self.finishProcessSignal.connect("finished", self.on_format_finished) # on finish img writing process
            self.cancelProcessId = self.cancelProcessSignal.connect("cancel", self.cancel_the_format_process) # for unknown problems while writing device

            self.content = self.get_object("formatResult")

            self.label_entry = self.get_object("name")
            self.label_entry_changed_id = self.label_entry.connect("changed", self.on_label_entry_text_changed)

            # Filesystemlist
            self.fsmodel = Gtk.ListStore(str, str, int, bool, bool)
            #                     id       label    max-length force-upper-case   force-alpha-numeric
            self.fsmodel.append(["fat32", "FAT32",      11,        True,                True])
            self.fsmodel.append(["ntfs",  "NTFS",       32,        False,               False])
            self.fsmodel.append(["ext4",  "EXT4",       16,        False,               False])
            self.filesystemlist.set_model(self.fsmodel)

            self.format_button = self.get_object("format_button")
            self.format_button.set_sensitive(False)
            self.format_button.connect("clicked", self.start_to_format)
            self.format_cancel_button = self.get_object("format_cancel_button")
            self.format_cancel_button.set_sensitive(False)
            self.format_cancel_button.connect("clicked", self.cancel_the_format_process)
            
            renderer_text = Gtk.CellRendererText()
            self.filesystemlist.pack_start(renderer_text, True)
            self.filesystemlist.add_attribute(renderer_text, "text", 1)

            # Devicelist model
            self.devicemodel = Gtk.ListStore(str, str)

            # Renderer
            renderer_text = Gtk.CellRendererText()
            self.devicelist.pack_start(renderer_text, True)
            self.devicelist.add_attribute(renderer_text, "text", 1) 

            self.filesystemlist.set_sensitive(True)
            # Default's to fat32
            self.filesystemlist.set_active(0)
            if filesystem is not None:
                iter = model.get_iter_first()
                while iter is not None:
                    value = model.get_value(iter, 0)
                    if value == filesystem:
                        self.filesystemlist.set_active_iter(iter)
                    iter = model.iter_next(iter)

        self.get_devices()
        self.window.show_all()
        self.window.connect("destroy", self.close)

    ######### ISO #########

    def get_devices(self, widget=None):
        if self.mode == "format":
            self.format_button.set_sensitive(False)

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
                                self.devicemodel.append([str(name), str(item)])

        self.devicelist.set_model(self.devicemodel)

    def selectDevice(self, widget):
        iter_ = self.devicelist.get_active_iter()
        if iter_ is not None:
            self.dev = self.devicemodel.get_value(iter_, 0)
            print("selectDevice : ", self.dev, "activeThread: ", activeCount())
            self.selectedTarget = self.dev
            if self.mode == "format":
                self.format_button.set_sensitive(True)

    def selectFile(self, widget):
        self.selectedFile =  self.chooser.get_filename()

    def updateBar(self, object, value, size, written):
        Gdk.threads_enter()
        # print("---UPDATEBAR----", value, size, written)
        self.bar.set_fraction(value)
        int_progress = int(float(value)*100)
        XApp.set_window_progress_pulse(self.window, False)
        XApp.set_window_progress(self.window, int_progress)
        self.size = size
        self.written = written
        Gdk.threads_leave()

    def start_to_write(self, widget):
        if self.dev is None or not os.path.exists(self.dev):
            # you must select a device
            self.show_dialog(_("Bir aygıt seçmelisiniz."))
            return
            
        if not os.path.exists(self.selectedFile):
            # you must select a disk image file
            self.show_dialog(_("Bir dosya seçmelisiniz."))
            return

        """
        device = parted.getDevice(self.selectedTarget)
        device_size = device.getLength() * device.sectorSize
        if (device.getLength() * device.sectorSize) < float(os.path.getsize(self.selectedFile)):
            # you must get enough space
            self.show_dialog(_("Yeteri kadar alan yok."))
            return
        """
               

        # self.file_closing()
        PROCESS_PERCENT.value = 0.0
        PROCESS_WRITTEN.value = 0.0
        PROCESS_SIZE.value = 0.0

        self.chooser.set_sensitive(False)
        self.devicelist.set_sensitive(False)
        self.cancelButton.set_sensitive(True)
        self.udisksCli.handler_block(self.udisksCliListener)

        
        self.playButton.disconnect(self.playId)
        self.playId = self.playButton.connect("clicked", self.pause)
        self.playButton.set_label(_("durdur"))

        self.content.get_buffer().set_text(_("%s , %s 'e yazılıyor..\n"%(self.selectedFile, self.selectedTarget)))

        self.sourceFileHandler = open(self.selectedFile, "rb")
        self.targetDeviceHandler = open(self.selectedTarget, "wb")
        self.total_size = os.path.getsize(self.selectedFile)

        self.updateBarThread = updateBarThread(self.updateBarSignal)
        self.updateBarThread.start()
        self.writeProcess = writeProcess(self.written,
                                        self.total_size,
                                        self.size,
                                        self.targetDeviceHandler, 
                                        self.sourceFileHandler,
                                        self.updateBarSignal,
                                        self.finishProcessSignal,
                                        self.cancelProcessSignal,
                                        self.window,
                                        self.playButton)
        self.check_job_thread = checkJobThread(self.writeProcess, self.finishProcessSignal)
        self.writeProcess.start()
        self.check_job_thread.start()
        # GObject.timeout_add(500, self.check_write_job)
        print("started: ", activeCount())

    def pause(self, obj):
        self.writeProcess.pause()
        print("waiting", self.writeProcess.is_alive(), "activeThread: ", activeCount())
        self.playButton.disconnect(self.playId)
        self.playButton.set_label(_("devam et"))
        self.playId = self.playButton.connect("clicked", self.continue_)

    def continue_(self, obj):
        print("not waiting", self.writeProcess.is_alive(), "activeThread", activeCount())
        self.playButton.disconnect(self.playId)
        self.playButton.set_label(_("durdur"))
        self.playId = self.playButton.connect("clicked", self.pause)
        self.writeProcess.continue_()

    def check_write_job(self):
        if self.writeProcess is not None:
            if self.writeProcess.exitcode is None:
                return True
            else:
                GObject.idle_add(self.write_job_done, self.writeProcess.exitcode)
                self.writeProcess = None
                return False

    def write_job_done(self, rc):
        if rc == 0:
            message = _('The image was successfully written.')
        elif rc == 1:
            message = _('The usb was successfully formatted.')
        elif rc == 4:
            message = _('An error occured while copying the image.')
        elif rc == 127:
            message = _('Authentication Error.')
        else:
            message = _('An error occurred.')
        self.logger(message)
        return message
        # self.show_dialog(message)

    def cancel_the_write_process(self, obj):
        # self.playButton.set_sensitive(False)
        self.check_job_thread.close_the_thread()
        self.updateBarThread.close_the_thread()
        self.writeProcess.cancel()
        self.writeProcess.terminate()
        time.sleep(0.1)
        print("[ Is thread live ] = ", self.writeProcess.is_alive())
        self.write_cancel()

    def write_cancel(self):
        self.get_devices()
        self.reset_first_values()
        self.set_iso_sensitive()
        self.logger(_("İptal Edildi"))

    def set_iso_sensitive(self):
        self.playButton.disconnect(self.playId)
        self.playId = self.playButton.connect("clicked",self.start_to_write)
        self.playButton.set_label(_("başla"))
        self.devicemodel.clear()
        self.udisksCli.handler_unblock(self.udisksCliListener)
        self.chooser.unselect_all()
        self.chooser.set_sensitive(True)
        self.devicelist.set_sensitive(True)
        self.playButton.set_sensitive(True)
        self.cancelButton.set_sensitive(False)
        self.get_devices()

    def reset_first_values(self):
        self.size = 0
        self.total_size = 0
        self.written = 0
        self.selectedFile = ""
        self.selectedTarget = ""

    def logger(self, word):
        text_buffer = self.content.get_buffer()
        end_iter = text_buffer.get_end_iter()
        text_buffer.insert(end_iter,_(word)) # text_buffer.insert(end_iter,_("İptal Edildi"))

    def on_write_finished(self, object, returncode):
        # a = time.time()
        self.updateBarThread.close_the_thread()
        message = self.write_job_done(returncode)
        print("returned message")
        # GObject.idle_add(self.file_closing)
        self.reset_first_values()
        print("reset first values")
        self.set_iso_sensitive()
        # b = time.time()
        # print(b-a)


    def close(self, object):
        try:
            if self.writeProcess is not None:
                self.check_job_thread.close_the_thread()
                self.updateBarThread.close_the_thread()
                self.writeProcess.terminate()
                # os.killpg(self.writeProcess.pid, signal.SIGTERM)
        except:
            pass
        finally:
            Gtk.main_quit()

    def file_closing(self):
        try:
            if (self.targetDeviceHandler is not None) and  (not self.targetDeviceHandler.closed):
                print(self.targetDeviceHandler, " open")
                self.targetDeviceHandler.close()
        except OSError:
            pass

        try:
            if (self.sourceFileHandler is not None) and (not self.sourceFileHandler.closed): 
                print(self.sourceFileHandler, " open")       
                self.sourceFileHandler.close()
        except OSError:
            pass

    def show_dialog(self, word):
        dialog = Dialogs(word, self.window)
        response = dialog.run()
        if response == Gtk.ResponseType.OK: 
            dialog.hide()
            return True
        return False

    ######### FORMAT #########
       
    def start_to_format(self, object):
        self.udisksCli.handler_block(self.udisksCliListener)
        self.devicelist.set_sensitive(False)
        self.filesystemlist.set_sensitive(False)
        self.format_button.set_sensitive(False)
        self.format_cancel_button.set_sensitive(True)

        label = self.label_entry.get_text()
        self.content.get_buffer().set_text(_("%s  formatting...\n"%(self.selectedTarget)))
        self.updateBarThread = updateBarThread(self.updateBarSignal, mode="format", bar=self.progressbar)
        self.updateBarThread.start()
        self.formatProcess = formatProcess(self.selectedTarget, self.filesystem, label, str(os.geteuid()), str(os.getgid()))
        self.check_job_thread = checkJobThread(self.formatProcess, self.finishProcessSignal)
        self.check_job_thread.start()
        self.formatProcess.start()

    def filesystem_selected(self, object):
        _iter = self.filesystemlist.get_active_iter()
        if _iter is not None:
            self.filesystem = self.fsmodel.get_value(_iter, 0)

            self.label_entry.set_max_length(self.fsmodel.get_value(_iter, 2))
            self.on_label_entry_text_changed(self, self.label_entry)

    def on_label_entry_text_changed(self, object, data=None):
        self.label_entry.handler_block(self.label_entry_changed_id)

        active_iter = self.filesystemlist.get_active_iter()
        value = self.fsmodel.get_value(active_iter, 0)

        if self.fsmodel.get_value(active_iter, 3):
            old_text = self.label_entry.get_text()
            new_text = old_text.upper()
            self.label_entry.set_text(new_text)

        if self.fsmodel.get_value(active_iter, 4):
            old_text = self.label_entry.get_text()

            for char in FORBIDDEN_CHARS:
                old_text = old_text.replace(char, "")

            new_text = old_text
            self.label_entry.set_text(new_text)

        length = self.label_entry.get_buffer().get_length()
        self.label_entry.select_region(length, -1)

        self.label_entry.handler_unblock(self.label_entry_changed_id)

    def cancel_the_format_process(self, object):
        pass

    def on_format_finished(self, object, returncode):
        self.updateBarThread.close_the_thread()
        # a = time.time()
        message = self.write_job_done(returncode)
        print("returned message")
        self.reset_first_values()
        print("reset first values")
        self.set_format_sensitive()
        # b = time.time()
        # print(b-a)

    def set_format_sensitive(self):
        self.get_devices()
        self.format_cancel_button.set_sensitive(False)
        self.filesystemlist.set_sensitive(True)
        self.devicelist.set_sensitive(True)
        self.udisksCli.handler_unblock(self.udisksCliListener)
        

    def activate_devicelist(self):
        self.devicelist.set_sensitive(True)
        self.expander.set_sensitive(True)
        self.label.set_sensitive(True)

def main(): 
    parser = argparse.ArgumentParser(description='milisImageWriter (milisImageWriter) <jarbay910@gmail.com>')
    parser.add_argument('-i', '--iso_path', dest='iso_path', help='Select the iso', type=str)
    parser.add_argument('-m', '--mode', dest='mode', help='select mode', type=str)  
    args = parser.parse_args()
    GObject.threads_init()
    Gdk.threads_init()
    if args.mode == "iso":
        if args.iso_path is not None:
            app = milisImageWriter(iso_path=args.iso_path, mode="iso")
        else:       
            app = milisImageWriter(mode="iso")
    elif args.mode == "format":
        app = milisImageWriter(mode="format")
    else:
        parser.print_help()
        return
    Gtk.main()
    Gdk.threads_leave()


if __name__ == "__main__":
    main()
    sys.exit()
