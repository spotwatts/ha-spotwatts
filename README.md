# Spotwatts for Home Assistant

Day-ahead electricity prices for the Nordic and Baltic price areas in Home Assistant: NO1–NO5, SE1–SE4, DK1–DK2,
FI, EE, LT and LV. 15-minute prices in your local currency, with or without VAT, and the cheapest 1–4 hour windows
from now. No account and no API key.

Prices come from the free [Spotwatts API](https://spotwatts.com/en/api), which publishes the SDAC auction results
from the ENTSO-E Transparency Platform.

## Installation

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=spotwatts&repository=ha-spotwatts&category=integration)

**Home Assistant 2026.11 and later:** **Marketplace → Add by link**, paste `https://github.com/spotwatts/ha-spotwatts`,
install **Spotwatts** and pick a price area. No restart needed.

**Earlier versions with HACS:**

1. In HACS, open the menu → **Custom repositories**, add `https://github.com/spotwatts/ha-spotwatts` as an
   **Integration**, then download **Spotwatts**.
2. Restart Home Assistant.
3. **Settings → Devices & services → Add integration → Spotwatts**, pick a price area.

Add the integration again for another price area. Manual installation: copy `custom_components/spotwatts` into your
`config/custom_components` folder and restart.

## Sensors

| Sensor | State | Attributes |
|---|---|---|
| Price | price of the current 15 minutes | `start`, `end`, `today`, `tomorrow`, `tomorrow_valid`, `raw_today`, `raw_tomorrow` |
| Average today / Lowest today / Highest today | price | `start`, `end` |
| Average tomorrow | price, unknown until the auction results are out (about 12:45 CET) | `start`, `end` |
| Cheapest hour, Cheapest 2 / 3 / 4 hours | start of the cheapest continuous window that starts now or later, also across midnight once tomorrow is known; a window that has begun is kept until it ends | `end`, `average_price` |

Prices are in the zone's currency per kWh (`NOK/kWh`, `SEK/kWh`, `DKK/kWh`, `EUR/kWh`), the spot price only:
no grid tariff, supplier mark-up or fees. VAT can be switched off in the integration's options; NO4 has no VAT on
household electricity.

`raw_today` and `raw_tomorrow` are lists of `{start, end, value}`, the same shape as the Nord Pool integration's, so
existing chart cards work with them. The price lists are not stored in the recorder.

## Examples

Run the dishwasher in the cheapest 3 hours:

```yaml
automation:
  - alias: Dishwasher in the cheapest 3 hours
    triggers:
      - trigger: time
        at: sensor.spotwatts_se3_cheapest_3_hours
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.dishwasher
```

Today and tomorrow with [ApexCharts Card](https://github.com/RomRider/apexcharts-card):

```yaml
type: custom:apexcharts-card
graph_span: 48h
span:
  start: day
now:
  show: true
series:
  - entity: sensor.spotwatts_se3_price
    type: column
    data_generator: |
      return [...entity.attributes.raw_today, ...entity.attributes.raw_tomorrow]
        .map((p) => [new Date(p.start).getTime(), p.value]);
```

## Removal

**Settings → Devices & services → Spotwatts**, open the menu of each price area and choose **Delete**. Then remove
Spotwatts in HACS (or delete `custom_components/spotwatts`) and restart Home Assistant.

## Data and terms

The integration asks the API for today's prices once a day and for tomorrow's every 15 minutes from 12:45 CET until
they are published; nothing else. The API is free, including for commercial use. If you show its prices publicly, for
example on a website, please add a visible link "Prices: Spotwatts" to <https://spotwatts.com>. See the
[terms](https://spotwatts.com/en/api#terms).

Not affiliated with Nord Pool or ENTSO-E.

## License

MIT
