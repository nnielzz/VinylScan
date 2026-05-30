"""Palette extraction and color enhancement helpers."""

from __future__ import annotations

import colorsys
from dataclasses import dataclass
from io import BytesIO
from math import sqrt

from PIL import Image, UnidentifiedImageError


class PaletteExtractionError(ValueError):
    """Raised when a palette cannot be extracted from an image."""


@dataclass(slots=True, frozen=True)
class PaletteColor:
    """A dominant color with weight."""

    rgb: tuple[int, int, int]
    weight: int


def extract_dominant_colors(
    image_bytes: bytes,
    *,
    max_colors: int,
    min_brightness: int,
    saturation_boost: float,
) -> list[tuple[int, int, int]]:
    """Extract the dominant colors from an image."""

    try:
        image = Image.open(BytesIO(image_bytes))
    except (UnidentifiedImageError, OSError) as err:
        raise PaletteExtractionError("Could not decode image data") from err

    image = image.convert("RGB")
    image.thumbnail((300, 300))

    quantized = image.quantize(colors=max(max_colors * 4, 12), method=Image.Quantize.MEDIANCUT)
    colors = quantized.convert("RGB").getcolors(maxcolors=300 * 300)

    if not colors:
        raise PaletteExtractionError("No colors found in image")

    weighted_colors = sorted(
        (
            PaletteColor(
                rgb=_enhance_color(rgb, min_brightness=min_brightness, saturation_boost=saturation_boost),
                weight=count,
            )
            for count, rgb in colors
            if _is_usable_color(rgb, min_brightness=min_brightness)
        ),
        key=lambda item: item.weight,
        reverse=True,
    )

    if not weighted_colors:
        raise PaletteExtractionError("Image did not contain usable light colors")

    filtered: list[tuple[int, int, int]] = []
    for color in weighted_colors:
        if any(_color_distance(color.rgb, existing) < 48 for existing in filtered):
            continue

        filtered.append(color.rgb)
        if len(filtered) >= max_colors:
            break

    if not filtered:
        raise PaletteExtractionError("No distinct colors left after filtering")

    return filtered


def _is_usable_color(rgb: tuple[int, int, int], *, min_brightness: int) -> bool:
    """Filter out colors that are too dark for a lamp."""

    red, green, blue = rgb
    value = max(rgb)
    perceived_luminance = int((0.2126 * red) + (0.7152 * green) + (0.0722 * blue))
    return value >= min_brightness and perceived_luminance >= min_brightness


def _enhance_color(
    rgb: tuple[int, int, int],
    *,
    min_brightness: int,
    saturation_boost: float,
) -> tuple[int, int, int]:
    """Boost saturation and slightly lift brightness to make colors fuller on lights."""

    red, green, blue = (channel / 255 for channel in rgb)
    hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)

    saturation = min(1.0, saturation * saturation_boost)
    if saturation > 0.08:
        saturation = max(saturation, 0.58)

    value_floor = max(min_brightness / 255, 0.32)
    value = max(value, value_floor)

    boosted = colorsys.hsv_to_rgb(hue, saturation, value)
    return tuple(int(channel * 255) for channel in boosted)


def _color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    """Return Euclidean distance between two RGB colors."""

    return sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def shift_hue(
    rgb: tuple[int, int, int],
    degrees: float,
    *,
    value_multiplier: float = 1.0,
) -> tuple[int, int, int]:
    """Return an RGB color with shifted hue and optional darker value."""

    red, green, blue = (channel / 255 for channel in rgb)
    hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)
    shifted_hue = (hue + (degrees / 360.0)) % 1.0
    shifted_value = min(1.0, max(0.0, value * value_multiplier))
    shifted = colorsys.hsv_to_rgb(shifted_hue, saturation, shifted_value)
    return tuple(int(channel * 255) for channel in shifted)
