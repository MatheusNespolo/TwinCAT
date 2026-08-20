import pyads
from ctypes import sizeof

ads_net_id="5.162.186.144.1.1"
plc=pyads.Connection(ads_net_id,pyads.PORT_TC3PLC1)

print("Connecting to TwinCAT PLC..")
plc.open()
print("Current connection status:",plc.is_open)
print("Current Status:",plc.read_state())

print("Closing the Connections..")
plc.close()
print("Current Status:",plc.is_open)
