from threading import Event, Thread
from queue import Queue 
import os
from signal import *
from notifications import *
from subprocess import Popen
from gi.repository import  GObject, Gdk #, Glib

class writeProcess(Thread):

    def __init__(self, qu, wid, content):
        Thread.__init__(self)
        self.play = True
        self.cancel_ = False
        self.kill = False

        self.data = qu
        self.bar = wid
        self.content = content
        

    def pause(self):
        """wait process"""
        self.play = False

    def continue_(self):
        """continue to process"""
        self.play = True

    def cancel(self):
        """cancel the process"""
        self.cancel_ = True

    def kill(self):
        """process kill,terminate program"""
        self.kill = True

    def getValues(self, qu):
        while(not qu.empty()):
            item = qu.get()
            print(item)
            print(item)
            yield item



    def run(self):
        self.isProcessStart, self.input_, self.output, self.size, self.written, self.total_size, self.increment, self.buffer_, self.signal = self.getValues(self.data)
        
        while not self.cancel_:
            Gdk.threads_enter()
            if self.play:
                if self.kill:
                    self.output.close()
                    self.input.close()
                    Gdk.threads_leave()
                    os.kill(os.getpid(), SIGKILL)#exit()  
                    #FIXME Which one is better,os.kill or exit func        
                
                if not self.isProcessStart:
                    self.total_size = os.path.getsize(self.input_)
                    self.input_ = open(self.input_, "rb")
                    self.output = open(self.output, "wb")

                    self.isProcessStart = True
                    self.size = 0
                    self.written = 0
                    self.increment = self.total_size / 100
            
                self.buffer_ = self.input_.read(1096)

                self.size += len(self.buffer_) 
                self.written += len(self.buffer_)

                if len(self.buffer_) == 0:
                    print("finished")
                    self.isProcessStart = False
                    self.cancel = True
                    self.play = False
                    self.output.flush()
                    self.input_.close()
                    self.output.close()  
                    Gdk.threads_leave()                 
                    break

                self.output.write(self.buffer_)
                if self.written >= self.increment:
                    self.output.flush()
                    self.written = 0
                print(float(self.size/self.total_size))
                self.bar.set_fraction(float(self.size/self.total_size))
                #self.bar.set_text("%s "%(str(float(self.size/self.total_size)*100) + "%"))
            Gdk.threads_leave()
            
                
        if self.cancel_:
            self.input_.close()
            self.output.close()
            self.bar.set_fraction(0.0)
            Gdk.threads_leave()
            return
        if self.size == self.total_size:
            """process is successfull"""
            print("successful")
            text_buffer = self.content.get_buffer()
            end_iter = text_buffer.get_end_iter()
            text_buffer.insert(end_iter,"Image is written successfully.")
            #show_notification("successfull", "Image is written successfully.") #show_notification("successfull", "Image writing is failed.") #FIXME in normal mod,notification popup show,but when runned this script with sudo,it is raising error
        else:
            """unknown error"""
            print("unknown error")          
            text_buffer = self.content.get_buffer()
            end_iter = text_buffer.get_end_iter()
            text_buffer.insert(end_iter,"Image writing is failed.")
            #show_notification("successfull", "Image writing is failed.") #FIXME in normal mod,notification popup show,but when runned this script with sudo,it is raising error
        self.input_.close()
        self.output.close()
        Gdk.threads_leave()
        self.signal()
    
            


        
            
