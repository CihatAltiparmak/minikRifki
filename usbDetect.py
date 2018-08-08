import dbus

__all__ = ("getAllUnixDevices")

def getAllUnixDevices():
    busSession = dbus.SessionBus()
    obj = busSession.get_object("org.gtk.vfs.UDisks2VolumeMonitor", "/org/gtk/Private/RemoteVolumeMonitor")
    iface = dbus.Interface(obj, "org.gtk.Private.RemoteVolumeMonitor")
    _listdevice_ = iface.List()
    devices = []

    for i in _listdevice_[0]:
        for j in i:
            if isinstance(j, dbus.Dictionary):
                try:
                    #FIXME How do is select USB devices better without third party?
                    
                    path = deviceList("/org/freedesktop/UDisks2/block_devices/"+j["unix-device"].lstrip("/dev/"))
                    result = findUSBDevices(path)
                    if result[0]:
                        devices.append([str(result[1].Get("org.freedesktop.UDisks2.Drive", "Vendor"))+" "+str(result[1].Get("org.freedesktop.UDisks2.Drive", "Model"))+" "+str(round(result[1].Get("org.freedesktop.UDisks2.Drive", "Size") / 10**9,1)) + " GB", str(j["unix-device"]), result[1].Get("org.freedesktop.UDisks2.Drive", "Size")])
                        
                except KeyError:
                    pass
    return devices
        
    
def deviceList(objectPath):
    busSys = dbus.SystemBus()
    obj = busSys.get_object("org.freedesktop.UDisks2", objectPath)
    iface = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
    return iface.Get("org.freedesktop.UDisks2.Block", "Drive")

def findUSBDevices(objectPath):
    busSys = dbus.SystemBus()
    obj = busSys.get_object("org.freedesktop.UDisks2", objectPath)
    iface = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
    return (iface.Get("org.freedesktop.UDisks2.Drive", "ConnectionBus") == "usb", iface)

getAllUnixDevices()
