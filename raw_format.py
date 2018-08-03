import dbus

def format(objectPath, formatOption="fat32"):
    bus = dbus.SystemBus()
    obj = bus.get_object("org.freedesktop.UDisks2", objectPath)
    ifaceFilesystem = dbus.Interface(obj, "org.freedesktop.UDisks2.Filesystem")
    ifaceFilesystem.Unmount({})
   
    ifaceBlock = dbus.Interface(obj, "org.freedesktop.UDisks2.Block")
    ifaceBlock.Format(formatOption)   #FIXME How can file format set? 
