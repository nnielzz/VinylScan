# VinylScan Palette

A Home Assistant custom integration that extracts the dominant colors from an album cover or other image and then plays them as color transitions on your lamps.

## What this integration does

- Reads a direct external image URL from a helper or sensor.
- Filters out near-black colors so your lights don't get an unusable "black" step.
- Boost the saturation so that colors look fuller on Hue lamps and LED strips.
- Plays the dominant colors as a series of transitions.
- Also offers a separate service to transition lamps to a specified color.

## Installation

1. Place 'custom_components/vinylscan' in your Home Assistant configuration folder.
2. Restart Home Assistant.
3. Add the integration via 'Settings -> Devices & services -> Integrations -> Add integration'.

## Configuration via UI

During setup you choose:

- `Image entity`: the helper/sensor whose state contains a direct image URL.
- 'Lights': the lamps or LED strip that should play the colors.
- `Color duration`: how long each dominant color remains active.
- `Transition duration`: how long the transition between color changes lasts.
- `Max colors`: how many dominant colors you want to get from the cover.
- `Minimum brightness`: filter for dark colors.
- 'Loop forever': let the palette run indefinitely until you stop it, turn off the lights or set a different color externally.
- `Hue shift`: subtle hue shift during playback of a color, with slightly darker shades for more dynamics.
- 'Saturation boost': multiplier for fuller colors on lamps.

## Services

### `vinylscan.play_image_palette`

Uses the set source or an override from the service call to extract the dominant colors from an image and play them on the lamps. With `loop_forever: true` the sequence continues to run until you call `vinylscan.stop_palette_playback`, turn off the lights or externally send a different color to the same lights.

Example:

```yaml
service: vinylscan.play_image_palette
dates: 
image_entity_id: sensor.current_album_cover 
light_entity_ids: 
- light.livingroom_strip 
- light.livingroom_standing_lamp 
color_duration: 6 
transition_duration: 2 
hue_shift_degrees: 5 
brightness_pct: 85
```

You can also send a URL directly:

```yaml
service: vinylscan.play_image_palette
dates: 
image_url: https://example.com/cover.jpg
```

For an infinite loop:

```yaml
service: vinylscan.play_image_palette
