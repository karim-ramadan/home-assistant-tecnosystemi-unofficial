"""Constants for the Tecnosistemi integration."""

DOMAIN = "tecnosystemi_unofficial"

CONF_IP = "ip"
CONF_PIN = "pin"
CONF_SERIAL = "serial"

COMMON_SUBNETS = ["192.168.1", "192.168.0", "192.168.4"]

# Operating mode name → device mode number
PRESET_MODE_MAP: dict[str, int] = {
    "Recupero": 1,
    "Estrazione": 2,
    "Immissione": 3,
    "Auto Umidità ☀": 4,
    "Auto Umidità ❄": 5,
    "Comfort Estate": 6,
    "Comfort Inverno": 7,
    "CO₂ Recupero": 8,
    "CO₂ Estrazione": 9,
    "Auto Umidità 2 ☀": 10,
    "Auto Umidità 2 ❄": 11,
    "Ricambio Naturale": 12,
}

MODE_TO_PRESET: dict[int, str] = {v: k for k, v in PRESET_MODE_MAP.items()}

# Ordered speed list used with HA percentage helpers (index 0 = slowest)
ORDERED_SPEED_LIST = ["1", "2", "3", "4", "5"]
