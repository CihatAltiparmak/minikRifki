import dbus

def show_notification(self, title, content):
    bus = dbus.SessionBus()
    obj = bus.get_object("org.freedesktop.Notifications", "/org/freedesktop/Notifications")
    iface = dbus.Interface(obj, "org.freedesktop.Notifications")
    iface.Notify("elma",1,"",title,content,[],{},2)

