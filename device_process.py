import dbus
from zipfile import ZipFile
import os

class ExtractProcessControl(ZipFile):
	def __init__(self, widget, *args):
		super().__init__(*args)
		self.widget = widget
		self.processBar = self.widget.progressBar
		self.totalVolume = 0
		self.work = 0
		for i in self.infolist():
			self.totalVolume += i.file_size
		
		self.processBar.setMaximum(self.totalVolume)
		self.processBar.setMinimum(0)
		self.processBar.setValue(self.work)

	def extract(self, member, path, *args):
		super().extract(member, path, *args)
		self.work += self.getinfo(member).file_size

	def extractall(self, path, *args):
		os.chmod(path, 33277)
		super().extractall(path, *args)
		#os.fchmod(path, "r")

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
		print(self.name, self.system[self.name])
		objSystem = self.busSystem.get_object("org.freedesktop.UDisks2", self.system[self.name])
		iface = dbus.Interface(objSystem, "org.freedesktop.UDisks2.Filesystem")
		iface.Unmount({})
		iface.SetLabel(self.name, {})

	def do_mount(self):
		objSystem = self.busSystem.get_object("org.freedesktop.UDisks2", self.system[self.name])
		iface = dbus.Interface(objSystem, "org.freedesktop.UDisks2.Filesystem")
		iface.Mount({})
		#iface.SetLabel(self.name, {})

	def do_format(self):
		objSystem = self.busSystem.get_object("org.freedesktop.UDisks2", self.system[self.name])
		iface = dbus.Interface(objSystem, "org.freedesktop.UDisks2.Block")
		iface.Format('vfat', {})
		iface = dbus.Interface(objSystem, "org.freedesktop.UDisks2.Filesystem")
		iface.SetLabel(self.name, {})
    	