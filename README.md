# Tecnosistemi Home Assistant Integration

Unofficial Home Assistant integration for **Tecnosistemi Pico** VMC (Mechanical Ventilation with Heat Recovery) units, controlled over the local network via UDP.

> [!WARNING]
> This is a community project based on reverse-engineering the official Android app. It is not affiliated with or endorsed by Tecnosistemi S.r.l.

## Features

- **Auto-discovery** of Tecnosistemi devices on the local network
- **Per-device PIN** authentication stored securely in HA config entries
- **Fan entity** — power on/off, fan speed (5 levels), 12 operating modes as presets
- **Sensors** — ambient temperature, external temperature, current humidity
- Local polling — no cloud, no account required

## Installation via HACS

1. In HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/<your-username>/tecnosystemi_unofficial` as an **Integration**
3. Install **Tecnosistemi** from HACS
4. Restart Home Assistant

## Manual Installation

Copy the `custom_components/tecnosystemi/` folder into your HA `config/custom_components/` directory, then restart.

## Setup

1. **Settings → Devices & Services → Add Integration → Tecnosistemi**
2. Choose **Discover devices** (automatic scan) or **Enter IP manually**
3. Enter the device PIN (default: `1234`)
4. Done — the device appears with its fan entity and sensors

## Entities

| Entity                               | Type   | Description                                        |
| ------------------------------------ | ------ | -------------------------------------------------- |
| `fan.<name>`                         | Fan    | Power, fan speed (20–100 %), operating mode preset |
| `sensor.<name>_ambient_temperature`  | Sensor | Indoor ambient temperature (°C)                    |
| `sensor.<name>_external_temperature` | Sensor | Outdoor/exhaust temperature (°C)                   |
| `sensor.<name>_humidity`             | Sensor | Current relative humidity (%)                      |

## Operating Modes (Fan Presets)

| Preset            | Description                                     |
| ----------------- | ----------------------------------------------- |
| Recupero          | Balanced supply + extraction with heat recovery |
| Estrazione        | Extraction only                                 |
| Immissione        | Supply only                                     |
| Auto Umidità ☀    | Humidity-controlled auto (summer)               |
| Auto Umidità ❄    | Humidity-controlled auto (winter)               |
| Comfort Estate    | Comfort — summer profile                        |
| Comfort Inverno   | Comfort — winter profile                        |
| CO₂ Recupero      | CO₂-triggered heat-recovery                     |
| CO₂ Estrazione    | CO₂-triggered extraction                        |
| Auto Umidità 2 ☀  | Secondary humidity auto (summer)                |
| Auto Umidità 2 ❄  | Secondary humidity auto (winter)                |
| Ricambio Naturale | Natural air exchange                            |

## Requirements

- Home Assistant 2024.1 or later
- [`tecnosystemy-unofficial`](https://pypi.org/project/tecnosystemy-unofficial/) (installed automatically)
- Device must be on the same local network as Home Assistant

## Related

- [tecnosystemy-unofficial](https://github.com/karimemam/tecnosystemi_unofficial) — the underlying Python library and CLI
