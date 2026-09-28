"""Constants for the 352 air-quality / fresh-air (新风) Home Assistant integration.

Reverse-engineered from the 352 app (com.bugull.threefivetwoaircleaner).
The G30/G45 fresh-air device is controlled over the local network using a
proprietary UDP protocol on port 11530.  No cloud connection is required.
"""

DOMAIN = "air_352"

# UDP transport
UDP_PORT = 11530  # 0x2d0a  (CleanerWifiProtocol.UDP_PORT)
UDP_TIMEOUT = 5.0

# Frame magic bytes
PRO_APP_COMPANY_CODE = 0xA1   # outer frame magic / protocol version
PRO_FRAME_VERSION = 0x04      # fixed version byte after 0xA1
PRO_DEVICE_COMPANY_CODE = 0xF1  # manufacturer / company code
PRO_DEVICE_STX = bytes([0xF0, 0x72])  # inner frame STX (CleanerWifiProtocol.PRO_DEVICE_STX)

# Default device attributes.  These are *per-device* values normally fetched
# from the 352 cloud device list (POST /api2/device/getDeviceList on
# wifi.352air.com).  Defaults below match the confirmed G30 unit:
#   deviceType=0x04, companyCode=0xF2, authCode=0xA31A
# The device echoes them in every status frame and silently rejects control
# frames that use a different identity (all earlier "no control" results were
# caused by using the X83-family identity F1/03/0504).
DEFAULT_DEVICE_TYPE_G30 = 0x04
DEFAULT_DEVICE_TYPE_G45 = 0x0A
DEFAULT_AUTH_CODE = 0xA31A  # 2-byte auth code written into the frame header
DEFAULT_COMPANY_CODE = 0xF2

# Supported models
MODELS = {
    "g30": "352 G30 新风",
    "g45": "352 G45 新风",
}
DEVICE_TYPE_BY_MODEL = {
    "g30": DEFAULT_DEVICE_TYPE_G30,
    "g45": DEFAULT_DEVICE_TYPE_G45,
}

# Air-volume control range in m3/h (verified on the unit: 40..300, step 10;
# 0x58 takes the direct 2-byte value).  Shared by the number entity and the
# fan's read-only percentage.
AIR_VOLUME_MIN = 40
AIR_VOLUME_MAX = 300

# Command prefixes (first payload byte after the inner-frame header).
# Each command is sent as controlDeviceCommand(device, prefix, value).
CMD_POWER = 0x5E   # power on/off          value: 0x00=on, 0x11=off
CMD_MODE = 0x51    # working mode          value: 1..5 (see MODES)
CMD_LIGHT = 0x56   # display light         value: 0x00=on, 0x11=off
CMD_PTC = 0x53     # auxiliary heat (辅热) value: 0/1/2
CMD_SPEED = 0x58   # air volume (风量)     value: 2-byte big-endian (controlNewFanDeviceCommand)
CMD_LOCK_CONTROL = 0x24  # child lock (WifiProtocol.CMD_LOCK_CONTROL; exact frame TBC)

# Power / light values (DeviceProtocol.ON_OFF, LIGHTS)
VALUE_ON = 0x00
VALUE_OFF = 0x11

# Working modes.  Standard G30: {1,2,3,5}; super-carbon filter G30 adds mode 4
# (the high nibble 0x10 encodes the "super carbon" filter type).
MODE_AUTO = 1
MODE_SLEEP = 2
MODE_TURBO = 3
MODE_4 = 4      # extra mode present on super-carbon G30 (exact name TBD)
MODE_MANUAL = 5

PRESET_MODES = {
    MODE_AUTO: "auto",
    MODE_SLEEP: "sleep",
    MODE_TURBO: "turbo",
    MODE_4: "mode_4",
    MODE_MANUAL: "manual",
}

# PTC / auxiliary heat levels (DeviceProtocol.PTCS = {0,1,2})
PTC_LEVELS = {
    0: "off",
    1: "low",
    2: "high",
}

# Child lock (DeviceProtocol.CHILD_LOCK = {0, 0x11})
CHILD_LOCK_ON = 0x11
CHILD_LOCK_OFF = 0x00

# Filter types (from response content byte 3 high nibble)
FILTER_STANDARD = 0x00
FILTER_SUPER_CARBON = 0x10
