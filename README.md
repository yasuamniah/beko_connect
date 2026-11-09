# Beko Connect for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=KULLANICI_ADI&repository=ha-beko-connect&category=integration)

Control **Beko air conditioners with the Wi-Fi module used by the Beko Connect app** (Cosa cloud) from Home Assistant, with live updates pushed from the cloud.

> **Unofficial.** This project is not affiliated with, endorsed by or supported by Beko, Arçelik or Cosa. It talks to the same cloud service the mobile app uses, so it may break whenever the manufacturer changes it. Use at your own risk.

🇹🇷 Türkçe açıklama için aşağıya bakın.

## Features

- **Climate entity**: on/off, modes (cool, heat, dry, fan only, auto), target temperature (16-30 °C, step 1), fan speed (auto, 1-5)
- **Live state**: the cloud pushes every change, including changes made with the remote control or the phone app (no polling delay)
- **Built-in temperature sensor** of the unit, usable for automations
- Air direction selectors (vertical and horizontal) and a Turbo switch
- Power sensor and error-code diagnostic
- Automatic reconnect if the connection to the cloud drops
- Works alongside the phone app (same account)

## Requirements

- Home Assistant 2024.2 or newer
- A Beko air conditioner that you can control with the **Beko Connect** app, and your app account (email + password)

## Installation

### HACS (recommended)

1. In Home Assistant open **HACS → ⋮ (top right) → Custom repositories**.
2. Add `https://github.com/yasuamniah/ha-beko-connect` with category **Integration**.
3. Search for **Beko Connect**, download it and **restart Home Assistant**.

### Manual

Copy the `custom_components/beko_connect` folder into your Home Assistant `config/custom_components/` folder and restart.

## Setup

1. **Settings → Devices & services → Add integration → Beko Connect**.
2. Sign in with the email and password of your Beko Connect app account.

Your password is stored in Home Assistant's own configuration and is only sent to the Beko cloud.

## Entities

| Entity | Type | Notes |
| --- | --- | --- |
| Air conditioner | `climate` | Modes, target temperature, fan speed |
| Internal temperature | `sensor` | Temperature sensor inside the unit/module |
| Power | `sensor` | Instantaneous power (W), 0 when the unit is off |
| Error code | `sensor` | Diagnostic |
| Last temperature update | `sensor` | Diagnostic, timestamp of the last reading |
| Vertical / Horizontal air direction | `select` | Same positions as in the app |
| Turbo | `switch` | "Hızlı Mod" in the app |
| Display light off | `binary_sensor` | Read-only, see limitations |
| Air clean, Auto drying | `switch` | Disabled by default; no effect on the tested model |

## Known limitations

- **The temperature is not reported while the unit is off.** The cloud keeps the last value, so the sensor goes stale. For automations that must work while the AC is off, use a separate room thermometer and use this integration only to control the AC. The *Last temperature update* sensor tells you how old the value is.
- Selecting a mode while the unit is off first powers it on, waits 2 seconds, then sets the mode (the unit ignores a mode sent while off). If the mode does not change on your unit, increase `POWER_ON_DELAY` in `const.py`.
- The unit resets the target temperature when the mode changes (for example 18 °C in cool, 30 °C in heat). Set the temperature after the mode.
- The display-light command is not exposed by the app and does not reach the unit, so it is read-only here.
- Developed and tested with one unit. The integration handles every device on the account but only a single device has been tested. Features may differ between models.

## Example automation

Start heating when the room gets cold, only if the reading is fresh (adjust the entity names):

```yaml
alias: Heat when cold
trigger:
  - platform: numeric_state
    entity_id: sensor.living_room_internal_temperature
    below: 26
  - platform: time_pattern
    minutes: "/10"
condition:
  - condition: numeric_state
    entity_id: sensor.living_room_internal_temperature
    below: 26
  - condition: state
    entity_id: climate.living_room
    state: "off"
  - condition: template
    value_template: >
      {{ (now() - states('sensor.living_room_last_temperature_update') | as_datetime).total_seconds() < 900 }}
action:
  - service: climate.set_temperature
    target:
      entity_id: climate.living_room
    data:
      hvac_mode: heat
      temperature: 26
```

A `numeric_state` trigger only fires when the value *crosses* the threshold, which is why the periodic trigger and the state conditions are used.

## Troubleshooting

Enable debug logs in `configuration.yaml`, restart and check **Settings → System → Logs**:

```yaml
logger:
  default: warning
  logs:
    custom_components.beko_connect: debug
```

When opening an issue, **remove personal data** from logs and outputs (email, password, device and user IDs, location, MAC address, tokens).

## How it works

The Beko Connect app talks to its cloud over a WebSocket (Socket.IO / Sails). This integration implements the same protocol with Home Assistant's built-in `aiohttp`, so it has no extra dependencies. After login it receives state changes as pushes and sends commands for each control; a full resync runs every 5 minutes as a safety net.

## License

[MIT](LICENSE)

---

<details>
<summary><b>🇹🇷 Türkçe</b></summary>

### Beko Connect – Home Assistant entegrasyonu

Beko Connect uygulamasıyla (Cosa bulutu) kontrol edilen **Beko klimaları** Home Assistant'tan yönetmenizi sağlar. Bulut her değişikliği anında gönderir (kumandayla ya da telefondan yapılanlar dahil).

> **Resmî değildir.** Beko, Arçelik veya Cosa ile bir bağlantısı yoktur. Mobil uygulamanın kullandığı bulut hizmetiyle konuşur, üretici değiştirirse çalışmayabilir. Kullanım sorumluluğu size aittir.

**Özellikler:** klima varlığı (aç/kapat, soğutma, ısıtma, nem alma, fan, otomatik, 16-30 °C hedef sıcaklık, fan hızı), cihazın dahili sıcaklık sensörü, dikey/yatay hava yönü, Hızlı Mod, güç ve hata kodu sensörleri, bağlantı koparsa otomatik yeniden bağlanma.

**Kurulum (HACS):**
1. HACS → sağ üstte ⋮ → **Özel depolar** (Custom repositories).
2. `https://github.com/yasuamniah/ha-beko-connect` adresini **Integration** kategorisiyle ekleyin.
3. "Beko Connect"i bulup indirin ve Home Assistant'ı **yeniden başlatın**.
4. **Ayarlar → Cihazlar ve hizmetler → Entegrasyon ekle → Beko Connect** ve Beko Connect uygulamasındaki e-posta/şifreyle giriş yapın.

**Bilinen sınırlamalar:**
- Klima **kapalıyken sıcaklık bildirilmez**, sensör son değerde kalır. Klima kapalıyken çalışması gereken otomasyonlar için ayrı bir oda termometresi kullanın. "Son sıcaklık güncellemesi" sensörü değerin ne kadar eski olduğunu gösterir.
- Klima kapalıyken mod seçilirse önce açılır, 2 saniye beklenir, sonra mod gönderilir. Mod değişmezse `const.py` içindeki `POWER_ON_DELAY` değerini artırın.
- Mod değişince cihaz hedef sıcaklığı sıfırlar; önce modu, sonra sıcaklığı ayarlayın.
- Ekran ışığı komutu cihaza ulaşmadığı için salt okunurdur. Hava temizleme ve otomatik kurutma test edilen modelde çalışmaz (varsayılan olarak kapalı).
- Tek cihazla test edilmiştir.

**Sorun bildirirken** günlüklerden e-posta, şifre, cihaz/kullanıcı kimlikleri, konum, MAC adresi ve token gibi kişisel bilgileri silin.

</details>
