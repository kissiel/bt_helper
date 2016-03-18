import dbus
import dbus.mainloop.glib
import sys
import logging
import time
from gi.repository import GObject

logger = logging.getLogger(__file__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)

IFACE = 'org.bluez.Adapter1'
ADAPTER_IFACE = 'org.bluez.Adapter1'
DEVICE_IFACE = 'org.bluez.Device1'

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

BT_ANY = 0
BT_KEYBOARD = int('0x2540', 16)

class BtDbusManager:
    def __init__(self):
        self._bus = dbus.SystemBus()
        self._bt_root = self._bus.get_object('org.bluez', '/')
        self._manager = dbus.Interface(
            self._bt_root, 'org.freedesktop.DBus.ObjectManager')

    def _get_objects_by_iface(self, iface_name):
        for path, ifaces in self._manager.GetManagedObjects().items():
            if ifaces.get(iface_name):
                yield self._bus.get_object('org.bluez', path)

    def get_bt_adapters(self):
        """Yields all found bluez adapter proxies."""
        for adapter in self._get_objects_by_iface(ADAPTER_IFACE):
            yield BtAdapter(dbus.Interface(adapter, ADAPTER_IFACE), self)

    def get_bt_devices(self, category=BT_ANY, filters={}):
        """Yields all bluez device proxies."""
        for device in self._get_objects_by_iface(DEVICE_IFACE):
            obj = self.get_object_by_path(device.object_path)[DEVICE_IFACE]
            try:
                if category != BT_ANY:
                    if obj['Class'] != category:
                        continue
                rejected = False
                for filter in filters:
                    if obj[filter] != filters[filter]:
                        rejected = True
                        break
                if rejected:
                    continue
                yield dbus.Interface(device, DEVICE_IFACE)
            except KeyError as exc:
                logger.info('Property %s not found on device %s',
                            exc, device.object_path)
                continue

    def get_prop_iface(self, obj):
        return dbus.Interface(self._bus.get_object(
            'org.bluez', obj.object_path), 'org.freedesktop.DBus.Properties')

    def get_object_by_path(self, path):
        return self._manager.GetManagedObjects()[path]

    def scan(self):
        self._bus.add_signal_receiver(interfaces_added,
                dbus_interface = "org.freedesktop.DBus.ObjectManager",
                signal_name = "InterfacesAdded")
        self._bus.add_signal_receiver(properties_changed,
                dbus_interface = "org.freedesktop.DBus.Properties",
                signal_name = "PropertiesChanged",
                arg0 = "org.bluez.Device1",
                path_keyword = "path")
        for adapter in self._get_objects_by_iface(ADAPTER_IFACE):
            try:
                dbus.Interface(adapter, ADAPTER_IFACE).StartDiscovery()
            except Exception as exc:
                if exc.get_dbus_name() == 'org.bluez.Error.InProgress':
                    logging.warning('Scan already in progress, restart it now')
                    dbus.Interface(adapter, ADAPTER_IFACE).StopDiscovery()
                    dbus.Interface(adapter, ADAPTER_IFACE).StartDiscovery()
                else:
                    logging.error('Unable to start scanning - {}'
                                  .format(exc.get_dbus_message())
        mainloop = GObject.MainLoop()
        mainloop.run()

class BtAdapter():
    def __init__(self, dbus_iface, bt_mgr):
        self._if = dbus_iface
        self._bt_mgr = bt_mgr
        self._prop_if = bt_mgr.get_prop_iface(dbus_iface)

    def set_bool_prop(self, prop_name, value):
        self._prop_if.Set(IFACE, prop_name, dbus.Boolean(value))

    def ensure_powered(self):
        powered = self._prop_if.Get(IFACE, 'Powered')
        logger.info('Powering on {}'.format(self._if.object_path.split('/')[-1]))
        if powered:
            logger.info('Device already powered')
            return
        try:
            self.set_bool_prop('Powered', True)
            logger.info('Powered on')
        except Exception as exc:
            logging.error('Failed to power on - {}'.format(exc.get_dbus_message()))

def properties_changed(interface, changed, invalidated, path):
    logger.info('Property changed for device @ %s. Change: %s', path, changed)
        
        
def interfaces_added(path, interfaces):
    logger.info('Added new bt interfaces: %s @ %s', interfaces, path)
