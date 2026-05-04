"""Constants for the Tecnosistemi integration."""

from tecnosystemi_unofficial.devices import MODE_LED_COLORS  # noqa: F401

DOMAIN = "tecnosystemi"

CONF_IP = "ip"
CONF_PIN = "pin"
CONF_SERIAL = "serial"

COMMON_SUBNETS = ["192.168.1", "192.168.0", "192.168.4"]

# Operating mode name → device mode number
# Emoji prefix matches the physical LED color for that mode.
PRESET_MODE_MAP: dict[str, int] = {
    "Recupero 🔵": 1,  # Turchese
    "Estrazione 🟢": 2,  # Verde
    "Immissione 🔴": 3,  # Fucsia
    "Auto Umidità ☀ 🟡": 4,  # Giallo
    "Auto Umidità ❄ ⚪": 5,  # Bianco
    "Comfort Estate 🟣": 6,  # Viola
    "Comfort Inverno 🟢": 7,  # Verde (CO₂)
    "CO₂ Recupero 🔵": 8,  # Blu
    "CO₂ Estrazione 🔵": 9,  # Blu scuro
    "Auto Umidità 2 ☀ 🟠": 10,  # Arancione
    "Auto Umidità 2 ❄ 🟣": 11,  # Viola chiaro
    "Ricambio Naturale ⚪": 12,  # Grigio
}

MODE_TO_PRESET: dict[int, str] = {v: k for k, v in PRESET_MODE_MAP.items()}

# Ordered speed list used with HA percentage helpers (index 0 = slowest)
ORDERED_SPEED_LIST = ["1", "2", "3", "4", "5"]
