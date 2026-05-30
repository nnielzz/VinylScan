# VinylScan Palette

Een Home Assistant custom integration die de dominante kleuren uit een album cover of andere afbeelding haalt en die vervolgens als kleurtransities afspeelt op je lampen.

## Wat deze integratie doet

- Leest een directe externe image URL uit een helper of sensor.
- Filtert bijna-zwarte kleuren weg zodat je lampen geen onbruikbare "zwart"-stap krijgen.
- Boost de saturatie zodat kleuren voller ogen op Hue lampen en ledstrips.
- Speelt de dominante kleuren als een reeks transities af.
- Biedt ook een losse service om lampen naar een opgegeven kleur te laten transitionen.

## Installatie

1. Plaats `custom_components/vinylscan` in je Home Assistant configuratiemap.
2. Herstart Home Assistant.
3. Voeg de integratie toe via `Instellingen -> Apparaten & diensten -> Integraties -> Voeg integratie toe`.

## Configuratie via UI

Tijdens de setup kies je:

- `Image entity`: de helper/sensor waarvan de state een directe image URL bevat.
- `Lights`: de lampen of ledstrip die de kleuren moeten afspelen.
- `Color duration`: hoe lang elke dominante kleur actief blijft.
- `Transition duration`: hoe lang de overgang tussen kleurwissels duurt.
- `Max colors`: hoeveel dominante kleuren je uit de cover wilt halen.
- `Minimum brightness`: filter voor donkere kleuren.
- `Loop forever`: laat het palette oneindig doorlopen totdat je het stopt, de lampen uitzet of extern een andere kleur zet.
- `Hue shift`: subtiele hue-verschuiving tijdens het afspelen van een kleur, met iets donkerdere shades voor meer dynamiek.
- `Saturation boost`: multiplier voor vollere kleuren op lampen.

## Services

### `vinylscan.play_image_palette`

Gebruikt de ingestelde bron of een override uit de service call om de dominante kleuren uit een afbeelding te halen en die op de lampen af te spelen. Met `loop_forever: true` blijft de reeks lopen totdat je `vinylscan.stop_palette_playback` aanroept, de lampen uitzet of extern een andere kleur naar dezelfde lampen stuurt.

Voorbeeld:

```yaml
service: vinylscan.play_image_palette
data:
  image_entity_id: sensor.current_album_cover
  light_entity_ids:
    - light.woonkamer_strip
    - light.woonkamer_staande_lamp
  color_duration: 6
  transition_duration: 2
  hue_shift_degrees: 5
  brightness_pct: 85
```

Je kunt ook rechtstreeks een URL meesturen:

```yaml
service: vinylscan.play_image_palette
data:
  image_url: https://example.com/cover.jpg
```

Voor een oneindige loop:

```yaml
service: vinylscan.play_image_palette
data:
  image_entity_id: sensor.current_album_cover
  loop_forever: true
  color_duration: 5
  transition_duration: 1.5
  hue_shift_degrees: 4
```

### `vinylscan.stop_palette_playback`

Stopt een actieve palette-playback. Handig als je `loop_forever` gebruikt, al stopt een loop nu ook automatisch bij `light.turn_off` of een externe kleurwijziging op dezelfde lampen.

```yaml
service: vinylscan.stop_palette_playback
data:
  light_entity_ids:
    - light.woonkamer_strip
```

### `vinylscan.transition_to_color`

Laat lampen transitionen naar een expliciete kleur, bruikbaar in automations.

```yaml
service: vinylscan.transition_to_color
data:
  light_entity_ids:
    - light.woonkamer_strip
  rgb_color: [255, 120, 20]
  transition_duration: 4
  brightness_pct: 100
```

Of met hex:

```yaml
service: vinylscan.transition_to_color
data:
  hex_color: "FF6A00"
  transition_duration: 2.5
```

## Automation voorbeeld

```yaml
alias: Speel albumcover kleuren af
triggers:
  - trigger: state
    entity_id: media_player.living_room
    attribute: media_title
actions:
  - action: vinylscan.play_image_palette
    data:
      image_entity_id: sensor.current_album_cover
      light_entity_ids:
        - light.woonkamer_strip
        - light.eettafel
      color_duration: 5
      transition_duration: 1.5
      hue_shift_degrees: 4
      brightness_pct: 90
mode: restart
```

## Opmerkingen

- De state van de gekozen entity moet een directe afbeeldings-URL zijn.
- Als je meerdere VinylScan config entries hebt, kun je `entry_id` meesturen aan een service call om expliciet de juiste defaults te kiezen.
