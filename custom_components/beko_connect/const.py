"""Constants for the Beko Connect integration (unofficial)."""
from datetime import timedelta

DOMAIN = "beko_connect"

# BekoApiError codes that mean "network/protocol problem", not "bad login".
TRANSPORT_CODES = {"timeout", "not_connected", "handshake_timeout", "connection_closed"}

# Seconds to wait after powering on before sending a mode: the unit seems to
# ignore a mode sent while it is off, so power goes first. Raise this if the
# mode still does not change when switching on from off.
POWER_ON_DELAY = 2

# Full resync in case a push was missed (pushes keep the state live in between).
RESYNC_INTERVAL = timedelta(minutes=5)

# Home Assistant fan mode -> acFanSpeed value (from the Beko Connect app code).
FAN_TO_VALUE = {"auto": 8, "1": 2, "2": 3, "3": 4, "4": 5, "5": 6}

# Air-direction option -> value sent to the cloud. Mapping verified by the
# user against the phone app: for the vertical flap the app label is 7 minus
# the value (label 1 = most open); the value for label 3 (4) is the one entry
# inferred from that pattern.
VERTICAL_SWING = {
    "off": 0, "pos_6": 1, "pos_5": 2, "pos_4": 3,
    "pos_3": 4, "pos_2": 5, "pos_1": 6, "auto": 100,
}
HORIZONTAL_SWING = {
    "off": 0, "far_left": 1, "left": 2, "center": 3, "right": 4,
    "far_right": 5, "left_center": 13, "right_center": 35, "auto": 100,
}
