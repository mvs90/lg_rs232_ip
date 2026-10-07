"""Constants for LG Display RS232/IP integration."""

DOMAIN = "lg_rs232_ip"
DEFAULT_PORT = 9761

# RS232 Protocol constants
DEFAULT_DEVICE_ID = 0x01
READ_STATUS = 0xFF  # Read only for commands that explicitly document FF.
COMMAND_TIMEOUT = 2.0  # 2 seconds for slower display responses
# Input sources (as hex values)
# The codes here are based on the observed xb response values for this display.
INPUT_SOURCES = {
    "HDMI 1": 0x90,
    "HDMI 2": 0x91,
    "HDMI 3": 0x92,
}

# Input detection candidates to automatically discover supported xb values.
# Based on user testing, these displays use 0x90-0x92 for HDMI inputs
INPUT_DETECTION_CANDIDATES = {
    "HDMI 1": [0x90],
    "HDMI 2": [0x91],
    "HDMI 3": [0x92],
}

PICTURE_MODES = {
    "mall": 0x00,
    "general": 0x01,
    "corporate": 0x02,
    "transportation": 0x03,
    "education": 0x04,
    "expert1": 0x05,
    "aps": 0x08,
    "calibration": 0x11,
    "hospital": 0x12,
}

ENERGY_SAVING_MODES = {
    "OFF": 0x00,
    "MINIMUM": 0x01,
    "MEDIUM": 0x02,
    "MAXIMUM": 0x03,
    "AUTO": 0x04,
}

SOUND_MODES = {
    "STANDARD": 0x01,
    "MUSIC": 0x02,
    "CINEMA": 0x03,
    "SPORTS": 0x04,
    "GAME": 0x05,
    "NEWS": 0x07,
}

OSD_LANGUAGES = {
    0x00: "CZECH",
    0x01: "DANISH",
    0x02: "GERMAN",
    0x03: "ENGLISH",
    0x04: "SPANISH",
    0x05: "GREEK",
    0x06: "FRENCH",
    0x07: "ITALIAN",
    0x08: "DUTCH",
    0x09: "NORWEGIAN",
    0x0A: "PORTUGUESE",
    0x0B: "PORTUGUESE (BRAZIL)",
    0x0C: "RUSSIAN",
    0x0D: "FINNISH",
    0x0E: "SWEDISH",
    0x0F: "KOREAN",
    0x10: "CHINESE (MANDARIN)",
    0x11: "JAPANESE",
    0x12: "CHINESE (CANTONESE)",
    0x13: "ARABIC",
}


POWER_TRANSITION_TIMEOUT = 20
