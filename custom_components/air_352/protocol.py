"""352 fresh-air (G30/G45) UDP protocol: frame building and response parsing.

Reverse-engineered from the 352 Android app
(com.bugull.threefivetwoaircleaner.network.wifi.newwifi.protocal).

Outer frame (built by ProtocolHeaderBuilder.assembleCommand):
    [0]    0xA1  magic / protocol version
    [1]    0x04
    [2:8]  device MAC (6 bytes)
    [8]    length = (flag + inner_payload length) + 7
    [9]    0x00
    [10:12]  sequence number (big-endian, 2 bytes)
    [12]   0xF1  company code
    [13]   device type
    [14:16] auth code (2 bytes)
    [16]   flag (1 for device types 2/3 and >4; 0 for 1/4)
    [17:]  inner payload

Inner payload (built by DeviceCommandBuilder.controlDeviceCommand):
    [0:2]  STX = F0 72
    [2:4]  length (big-endian, = payload length - 2)
    [4]    device type
    [5]    0x04
    [6]    0x02
    [7:9]  command sequence number (big-endian, 2 bytes)
    [9]    0x03
    [10]   command prefix
    [11]   value (or value high byte for 2-byte commands)
    [12]   0x00 (or value low byte for 2-byte commands)
    [13:15] CRC-16 (over bytes [2:13])

CRC-16 (ByteUtil.crc16Calc): init 0xFFFF, poly 0x1021, MSB-first,
final complement (the "GENIBUS" variant), result stored big-endian.
"""

from __future__ import annotations

from dataclasses import dataclass


def crc16(data: bytes) -> bytes:
    """Compute the 352 CRC-16 (GENIBUS variant) and return 2 bytes (big-endian)."""
    crc = 0xFFFF
    for byte in data:
        for bit in range(8):
            flag = ((0x8000 & crc) >> 8) ^ ((byte << bit) & 0x80)
            crc = (crc << 1) & 0xFFFF
            if flag:
                crc ^= 0x1021
    crc = (~crc) & 0xFFFF
    return bytes([(crc >> 8) & 0xFF, crc & 0xFF])


def mac_hex_to_bytes(mac: str) -> bytes:
    """'AA:BB:CC:DD:EE:FF' -> b'\\xaa\\xbb\\xcc\\xdd\\xee\\xff'."""
    return bytes.fromhex(mac.replace(":", "").replace("-", ""))


def build_inner_command(
    device_type: int, command_seq: int, prefix: int, value: int, two_byte_value: bool = False
) -> bytes:
    """Build the inner (CRC-protected) control frame for controlDeviceCommand."""
    payload = bytearray(15)
    payload[0:2] = bytes([0xF0, 0x72])  # STX
    payload[2] = 0x00
    payload[3] = 15 - 2  # length of everything after the length field
    payload[4] = device_type & 0xFF
    payload[5] = 0x04
    payload[6] = 0x02
    payload[7] = (command_seq >> 8) & 0xFF
    payload[8] = command_seq & 0xFF
    payload[9] = 0x03
    payload[10] = prefix & 0xFF
    if two_byte_value:
        payload[11] = (value >> 8) & 0xFF
        payload[12] = value & 0xFF
    else:
        payload[11] = value & 0xFF
        payload[12] = 0x00
    payload[13:15] = crc16(bytes(payload[2:13]))
    return bytes(payload)


def build_frame(
    mac: str,
    device_type: int,
    auth_code: int,
    outer_seq: int,
    command_seq: int,
    prefix: int,
    value: int,
    two_byte_value: bool = False,
    company_code: int = 0xF2,
) -> bytes:
    """Build a complete control frame ready to send over UDP.

    company_code/device_type/auth_code are the *per-device* identity returned
    by the 352 cloud device list (e.g. G30: F2/04/A31A) and echoed by the
    device in every status frame; control frames with the wrong identity are
    silently rejected by the device.
    """
    mac_bytes = mac_hex_to_bytes(mac)
    inner = build_inner_command(device_type, command_seq, prefix, value, two_byte_value)

    flag = 1  # observed working value (the device echoes 0x01 after its header)

    # Length byte as the confirmed-working frames use: inner_len + 7 (0x16 for
    # the 15-byte inner frame; the flag byte is NOT counted).
    length = len(inner) + 7

    frame = bytearray()
    frame.append(0xA1)
    frame.append(0x04)
    frame += mac_bytes
    frame.append(length & 0xFF)
    frame.append(0x00)
    frame += (outer_seq & 0xFFFF).to_bytes(2, "big")
    frame.append(company_code & 0xFF)  # company code
    frame.append(device_type & 0xFF)
    frame += (auth_code & 0xFFFF).to_bytes(2, "big")
    frame.append(flag)
    frame += inner
    return bytes(frame)


@dataclass
class DeviceState:
    """Parsed state from a device status response."""

    power: bool | None = None
    mode: int | None = None
    filter_super_carbon: bool | None = None
    timer: int | None = None
    air_quality: int | None = None
    child_lock: bool | None = None
    light: bool | None = None
    pm25: int | None = None
    temperature: int | None = None
    humidity: int | None = None
    co2: int | None = None
    ptc: int | None = None
    wind_speed: int | None = None
    total_online_time: int | None = None
    air_total_value: int | None = None
    total_purification: int | None = None
    raw: bytes | None = None


def parse_response(packet: bytes) -> DeviceState | None:
    """Parse a device status broadcast (empirically calibrated against a real G30).

    Real device status frame (confirmed live):
        [0:2]  a1 06                     (magic + device->app)
        [2:8]  device MAC
        [8:10] length + 0x00
        [10:17]... outer fields
        stx     f0 72                     (inner frame start)
        [stx+2:stx+4] inner length
        content = packet[stx+7 : -2]     (status fields)
        [-2:]   CRC-16 over packet[stx+2 : -2]  (GENIBUS variant, validated)

    Returns None if the packet is not a recognised status frame.
    """
    if not packet or len(packet) < 0x20:
        return None
    if packet[0] != 0xA1:
        return None

    stx = packet.find(b"\xf0\x72", 4)
    if stx < 0 or stx + 7 + 29 > len(packet):
        return None

    # CRC check (validated live: crc16(packet[stx+2:-2]) == packet[-2:])
    if crc16(packet[stx + 2 : -2]) != packet[-2:]:
        return None

    content = packet[stx + 7 : -2]
    if len(content) < 29:
        return None

    state = DeviceState(raw=packet)

    # Byte 3 of content: low nibble = mode, high nibble = filter type.
    b3 = content[3]
    state.mode = b3 & 0x0F
    state.filter_super_carbon = (b3 & 0xF0) == 0x10

    state.timer = content[5]
    state.air_quality = content[6]
    state.child_lock = content[7] == 0x11
    state.light = content[8] == 0x00       # 0x00 = light on, 0x11 = off (observed toggling)
    state.power = content[9] == 0x00       # 0x00 = running (observed), 0x11 = standby

    state.pm25 = (content[12] << 8) | content[13]
    state.temperature = content[14] if content[14] < 128 else content[14] - 256
    state.humidity = content[15]
    state.co2 = (content[16] << 8) | content[17]
    state.ptc = content[18]

    if len(content) >= 29:
        state.wind_speed = (content[27] << 8) | content[28]

    # Filter / cumulative values (offsets follow the app's G30DataParser).
    if len(content) >= 27:
        mult = [1, 10, 100, 1000][content[21]] if content[21] < 4 else 1
        state.air_total_value = ((content[22] << 8) | content[23]) * mult
    if len(content) >= 27:
        mult2 = [1, 10, 100, 1000][content[24]] if content[24] < 4 else 1
        state.total_purification = ((content[25] << 8) | content[26]) * mult2

    return state
