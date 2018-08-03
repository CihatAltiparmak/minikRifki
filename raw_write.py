"""
import asyncio, functools
# event trigger function
def trigger(event):
    print('EVENT SET')
    input("bekleme kaldirilsin?")
    event.set() # wake up coroutines waiting

# event consumers
async def writeImage(event):
    consumer_name = 'Consumer A'
    #do write and go to control
    await event.wait()
    print('{} triggered'.format(consumer_name))

async def controlPlay(event):
    consumer_name = 'Consumer B'
    print('{} waiting'.format(consumer_name))
    while 1:
        await event.wait()
        print('{} triggered'.format(consumer_name))
        trigger(event)
# event
event = asyncio.Event()


main_future = asyncio.wait([consumer_a(event),
consumer_b(event)])
# event loop
event_loop = asyncio.get_event_loop()
event_loop.call_later(0.1, functools.partial(trigger, event))
# trigger event in 0.1 sec
# complete main_future
done, pending = event_loop.run_until_complete(main_future)
"""

from threading import *

class b(Event):

    def __init__(self):
        super().__init__()
        #self.my_func()
    def my_func(self):
        #print("************************************")
        #print("bir şey gir")
        self.wait()
        print("devam ediyor")
        print("----------------------------")
            
    def trigger(self):        
        self.set()
        #self.clear()
        
        


class par:
    def __init__(self):
        self.aj = b()
        self.part = Thread(target=self.g)
        self.part.daemon = True
        self.part.start()

    def g(self):
        self.aj.my_func()

    def eventStop(self):
        self.aj.trigger()
        self.aj = b()
        self.aj.my_func()
         
        
    

w = par()  

while 1:
    cev = input("e/h")
    if cev == "e":
        w.eventStop()
    else:
        break
    




























