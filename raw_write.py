from threading import Event, Thread
from queue import Queue 
import os

class writeProcess(Thread):

    def __init__(self, qu, wid):
        Thread.__init__(self)
        self.control = Event()
        self.data = qu
        self.bar = wid

    #def cancel(self):
        #self.control.set()

    def getValues(self, qu):
        while(not qu.empty()):
            item = qu.get()
            print(item)
            print(item)
            yield item


    def continue_(self):
        print("continue da")
        self.play = True
        self.control.wait(0.05)
        self.control.set()
        self.control = Event()
        #self.run()
        
    def pause(self):
        print("pause da")
        self.blockkill = True
        self.play = False
        self.control.wait(0.01)  # self.control.wait() must not run here,because program isn't answer,instead i used self.control.wait(0.01)
    
    def kill(self):
        self.t.cancel()
        self.control.wait(0.01)
         
        
        
    def cancel(self):
        """process kill"""
        self.kill = True
        self.control.wait(0.01)  # self.control.wait() must not run here,because program isn't answer,instead i used self.control.wait(0.01)

    def setQue(self, *args):
        result_qu =Queue()
        for i in args: 
            result_qu.put(i)
        return result_qu

    def run(self):
        self.isProcessStart, self.input_, self.output, self.size, self.written, self.total_size, self.increment, self.buffer_ = self.getValues(self.data)
        self.play = True
        self.kill = False
        self.blockkill = False
        while True:
            if self.play:
                if not self.play:
                    self.wait()
                if self.kill:
                    break

                
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

                    self.output.flush()
                    self.input_.close()
                    self.output.close()
                    self.control.set()
                    break

                self.output.write(self.buffer_)
                if self.written >= self.increment:
                    self.output.flush()
                    self.written = 0
                print(float(self.size/self.total_size))
                self.bar.set_fraction(float(self.size/self.total_size))
                
            #self.data = self.setQue(self.isProcessStart, self.input_, self.output, self.size, self.written, self.total_size, self.increment, self.buffer_)
        if self.blockkill:
            exit()        

    
    
            


        
            
