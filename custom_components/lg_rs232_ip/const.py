"""Constants for LG Display RS232/IP integration."""

DOMAIN = "lg_rs232_ip"
DEFAULT_PORT = 9761

# RS232 Protocol constants
DEFAULT_DEVICE_ID = 0x01
READ_STATUS = 0xFF  # Special value to read current status without changing
COMMAND_TIMEOUT = 2.0  # 2 seconds for slower display responses
# Format: "command_name": "command_code"
RS232_COMMANDS = {
    # Power
    "power": "ka",
    "power_on": "ka",
    "power_off": "ka",
    # Volume & Mute
    "volume": "kf",
    "volume_mute": "ke",
    "volume_up": "mc",
    "volume_down": "mc",
    "mute": "ke",
    "unmute": "ke",
    # Info and OSD navigation
    "info_display": "mc",
    "menu": "mc",
    "button_up": "mc",
    "button_down": "mc",
    "button_right": "mc",
    "button_left": "mc",
    "enter": "mc",
    "return_key": "mc",
    "exit": "mc",
    # Picture settings
    "picture_size_just_scan": "kc",
    # Additional picture settings
    "aspect_ratio": "kc",
    "zoom": "kw",
    "picture_position": "kx",
    "picture_reset": "ky",
    # Audio settings
    "sound_output": "dv",
    "sound_select": "dy",
    "sound_mode": "dy",
    "balance": "kt",
    "bass": "ks",
    "treble": "ku",
    # Network and communication
    "network_status": "nz",
    "ip_address": "na",
    "subnet_mask": "nb",
    "gateway": "nc",
    "dns_server": "nd",
    "mac_address": "ne",
    "hostname": "nf",
    # System information
    "model_name": "ng",
    "firmware_version": "fw",
    "serial_number": "fy",
    "software_version": "fz",
    "manufacturing_date": "fm",
    "usage_time": "ft",
    # Advanced settings
    "fan_control": "dw",
    "temperature_control": "dt",
    "power_consumption": "dp",
    "lamp_control": "dl",
    "signal_detection": "sd",
    # Scheduling and timers
    "schedule_mode": "fs",
    "schedule_time": "ft",
    "holiday_mode": "fh",
    "power_on_timer": "fb",
    "power_off_timer": "fc",
    "auto_power": "fa",
    # Display protection
    "screen_saver": "sp",
    "pixel_shift": "ps",
    "inversion": "iv",
    "orbiter": "or",
    "white_wash": "ww",
    # Input settings
    "input_label": "il",
    "input_priority": "ip",
    "hdmi_hdcp": "hc",
    "cec_control": "ce",
    # Tile mode commands (require tile mode to be active)
    "tile_mode": "dd",
    "tile_id_set": "di",
    "tile_columns": "dg",
    "tile_rows": "dh",
    "tile_h_position": "de",
    "tile_v_position": "df",
    "tile_natural_mode": "dj",
    # Auto features
    "auto_sleep": "fg",
    "auto_adjustment": "ju",
    "auto_volume": "du",
    # Display settings
    "backlight": "mg",
    "brightness": "kh",
    "color": "ki",
    "color_temperature": "xu",
    "contrast": "kg",
    # Power management
    "dpm": "fj",
    "energy_saving": "jq",
    # Information
    "elapsed_time": "dl",
    "serial_number": "fy",
    "software_version": "fz",
    # Picture settings
    "picture_mode": "dx",
    "sharpness": "kk",
    "tint": "kj",
    # Audio settings
    "sound_mode": "dy",
    # Menu & Display
    "osd_select": "kl",
    "osd_language": "fi",
    "screen_mute": "kd",
    # Input
    "input": "xb",
    # Other features
    "ism_method": "jp",
    "temperature_value": "dn",
    "v_size": "ft",
    "abnormal_state": "kz",
    "power_on_delay": "fh",
    "remote_lock": "km",
    "time": "fa",
}

# Known non-working commands (No Response or negative results)
DISABLED_COMMANDS = {
    "aspect_ratio": "kc",  # NG
    "3d": "xt",  # No Response
    "2d_extended": "xv",  # No Response
    "auto_volume": "du",  # No Response
    "speaker": "dv",  # NG
    "balance": "kt",  # NG
    "bass": "ks",  # No Response
    "color_temperature_old": "ku",  # No Response
    "fan_fault_check": "dw",  # NG
    "h_position": "fq",  # NG
    "h_size": "fs",  # NG
    "input2": "kb",  # No Response
    "ir_key_code": "mc",  # NG
    "lamp_fault_check": "dp",  # No Response
    "natural_mode": "dj",  # NG
    "power_indicator": "fo",  # NG
    "power_saving": "fl",  # No Response
    "sleep_time": "ff",  # No Response
    "tile_h_position": "de",  # No Response
    "tile_h_size": "dg",  # No Response
    "tile_v_position": "df",  # No Response
    "tile_v_size": "dh",  # No Response
    "treble": "kr",  # No Response
    "v_position": "fr",  # NG
    "auto_configuration": "ju",  # NG
    "reset": "fk",  # NG
    "scheduled_input": "fu",  # NG
    "on_timer_on_off": "fb",  # NG
    "off_timer_on_off": "fc",  # NG
    "on_timer_time": "fd",  # NG
    "off_timer_time": "fe",  # NG
}

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
    "VIVID": 0x01,
    "STANDARD": 0x02,
    "CINEMA": 0x03,
    "SPORTS": 0x04,
    "GAME": 0x05,
    "HDR": 0x06,
    "FILMMAKER": 0x07,
    "ECO": 0x08,
}

ENERGY_SAVING_MODES = {
    "OFF": 0x00,
    "MINIMUM": 0x01,
    "MEDIUM": 0x02,
    "MAXIMUM": 0x03,
}

SOUND_MODES = {
    "STANDARD": 0x01,
    "MUSIC": 0x02,
    "CINEMA": 0x03,
    "SPORTS": 0x04,
    "GAME": 0x05,
}

OSD_LANGUAGES = {
    0x00: "ENGLISH",
    0x01: "FRENCH",
    0x02: "GERMAN",
    0x03: "SPANISH",
    0x04: "ITALIAN",
    0x05: "PORTUGUESE",
    0x06: "CHINESE",
    0x07: "JAPANESE",
    0x08: "KOREAN",
    0x09: "RUSSIAN",
}

ABNORMAL_STATES = {
    0x00: "NORMAL",
    0x01: "ABNORMAL",
}

REMOTE_LOCK_STATES = {
    0x00: "UNLOCKED",
    0x01: "LOCKED",
}

AUTO_SLEEP_STATES = {
    0x00: "OFF",
    0x01: "ON",
}

# Commands to skip during automated testing (dangerous or cause device to not respond)
SKIP_TEST_COMMANDS = {
    "power",  # Can cause device to become unresponsive
    "power_on",
    "power_off",
    "tile_mode",  # Can change display configuration
    "tile_id_set",  # Changes tile configuration
    "tile_columns",  # Changes tile configuration
    "tile_rows",  # Changes tile configuration
    "tile_h_position",  # Changes tile configuration
    "tile_v_position",  # Changes tile configuration
    "network_status",  # Network configuration
    "ip_address",  # Network configuration
    "subnet_mask",  # Network configuration
    "gateway",  # Network configuration
    "dns_server",  # Network configuration
    "hostname",  # Network configuration
    "schedule_mode",  # Scheduling configuration
    "schedule_time",  # Scheduling configuration
    "power_on_timer",  # Timer configuration
    "power_off_timer",  # Timer configuration
    "auto_power",  # Auto power configuration
    "screen_saver",  # Protection features
    "pixel_shift",  # Protection features
    "inversion",  # Protection features
    "orbiter",  # Protection features
    "white_wash",  # Protection features
    "fan_control",  # Hardware control
    "temperature_control",  # Hardware control
    "cec_control",  # HDMI control
    "hdmi_hdcp",  # HDMI control
}

# Fixed-value commands that require a specific parameter value
FIXED_COMMAND_PARAMS = {
    "power_on": 0x01,
    "power_off": 0x00,
    "volume_up": 0x02,
    "volume_down": 0x03,
    "mute": 0x00,
    "unmute": 0x01,
    "info_display": 0xAA,
    "menu": 0x43,
    "button_up": 0x40,
    "button_down": 0x41,
    "button_right": 0x06,
    "button_left": 0x07,
    "enter": 0x44,
    "return_key": 0x28,
    "exit": 0x5B,
    "picture_size_just_scan": 0x09,
    "aspect_ratio": 0x02,  # 16:9
    "zoom": 0x64,  # 100%
    "sound_output": 0x00,  # Internal
    "sound_select": 0x01,  # Standard
    "balance": 0x32,  # Center
    "bass": 0x32,  # Center
    "treble": 0x32,  # Center
    "tile_mode": 0x01,  # Active
    "tile_id_set": 0x01,  # ID 1
    "tile_columns": 0x01,  # 1 column
    "tile_rows": 0x01,  # 1 row
    "tile_h_position": 0x00,  # Position 0
    "tile_v_position": 0x00,  # Position 0
    "auto_sleep": 0x01,  # On
    "auto_adjustment": 0x01,  # On
    "auto_volume": 0x01,  # On
    "screen_saver": 0x00,  # Off
    "pixel_shift": 0x00,  # Off
    "inversion": 0x00,  # Off
    "orbiter": 0x00,  # Off
    "white_wash": 0x00,  # Off
    "hdmi_hdcp": 0x01,  # On
    "cec_control": 0x00,  # Off
    "schedule_mode": 0x00,  # Off
    "holiday_mode": 0x00,  # Off
    "power_on_timer": 0x00,  # Off
    "power_off_timer": 0x00,  # Off
    "auto_power": 0x00,  # Off
}

# Legacy command constants (for backwards compatibility)
INPUT_HDMI1 = 0x21
INPUT_HDMI2 = 0x22
INPUT_HDMI3 = 0x23
INPUT_DVI = 0x18
INPUT_RGB = 0x17
INPUT_S_VIDEO = 0x16
INPUT_COMPOSITE = 0x19

POWER_TRANSITION_TIMEOUT = 20

# Command power constants
CMD_POWER_ON = "ka 01 01"
CMD_POWER_OFF = "ka 01 00"
