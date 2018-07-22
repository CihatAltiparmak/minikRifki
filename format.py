import dbus

class DeviceManage:
	"""device control"""
	def __init__(self, deviceLabel):	
		self.busSystem = dbus.SystemBus()
		self.busSession = dbus.SessionBus()
		self.system = self.getReady(deviceLabel)
		self.name = deviceLabel


	def getReady(self, name):
		partSystem = {}
		objSession = self.busSession.get_object("org.gtk.vfs.UDisks2VolumeMonitor",
                                                    "/org/gtk/Private/RemoteVolumeMonitor")
		ifaceSession = dbus.Interface(objSession, "org.gtk.Private.RemoteVolumeMonitor")
		for i in ifaceSession.List()[1]:
			print("******************************************")
			for j in i:
				if isinstance(j, dbus.Dictionary):
					for k in j:
						if j[k] == name:
							print(j[k], j['unix-device'])
							print(j['unix-device'].lstrip(r"/dev/"))
							partSystem[j[k]] = "/org/freedesktop/UDisks2/block_devices/" + j['unix-device'].lstrip(r"/dev/")
							print("---------------------------------")
		return partSystem

	def do_umount(self):
		objSystem = self.busSystem.get_object(self.system[self.name])
		iface = dbus.Interface(objSystem, "org.freedesktop.UDisks2.Filesystem")
		iface.Unmount({})

	def do_mount(self):
		objSystem = self.busSystem.get_object("org.freedesktop.UDisks2")

	def do_format(self):
		objSystem = self.busSystem.get_object(self.system[self.name])
		iface = dbus.Interface(objSystem, "org.freedesktop.UDisks2.Block")
		iface.Format('vfat', {})
		iface = dbus.Interface(objSystem, "org.freedesktop.UDisks2.Filesystem")
		iface.SetLabel(self.name, {})
    	