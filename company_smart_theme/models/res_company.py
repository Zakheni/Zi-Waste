"""Company-level theme configuration extracted from logo palette."""

import base64
import logging
import re
from io import BytesIO
from collections import Counter

from PIL import Image
from odoo import api, fields, models
from odoo.tools.image import image_process

_logger = logging.getLogger(__name__)

DEFAULT_THEME_COLOR = "#4CAF50"
FALLBACK_PALETTE = ["#4CAF50", "#388E3C", "#81C784", "#A5D6A7"]
SVG_COLOR_RE = re.compile(
    r"(?:fill|stroke|stop-color|color)\s*=\s*['\"](#[0-9a-fA-F]{3,6}|"
    r"rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\))['\"]",
    re.IGNORECASE,
)
HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,6}\b")

try:
    from colorthief import ColorThief
except ImportError:  # pragma: no cover - declared in manifest external_dependencies
    ColorThief = None


def _normalize_hex(hex_color):
    hex_color = (hex_color or "").strip().lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(ch * 2 for ch in hex_color)
    if len(hex_color) != 6:
        return None
    try:
        int(hex_color, 16)
    except ValueError:
        return None
    return f"#{hex_color.lower()}"


def _rgb_to_hex(r, g, b):
    return "#%02x%02x%02x" % (int(r), int(g), int(b))


def _decode_logo_bytes(logo):
    try:
        image_data = base64.b64decode(logo)
    except Exception:
        return b""
    stripped = image_data.lstrip()
    if stripped.startswith(b"data:"):
        try:
            image_data = base64.b64decode(stripped.split(b",", 1)[1])
        except Exception:
            return b""
    # Some uploads store base64-encoded payload twice.
    try:
        if image_data and image_data[:1] not in (b"<", b"\x89", b"\xff", b"G", b"R"):
            second = base64.b64decode(image_data, validate=False)
            if second[:1] in (b"<", b"\x89", b"\xff", b"G", b"R") or (
                second[:4] == b"RIFF" and second[8:15] == b"WEBPVP8"
            ):
                image_data = second
    except Exception:
        pass
    return image_data


def _normalize_logo_raster(image_data):
    """Convert supported logo bytes to PNG bytes suitable for palette extraction."""
    if not image_data:
        return b""

    if image_data[:1] == b"<":
        return b""

    try:
        processed = image_process(image_data, size=(150, 150), output_format="PNG")
        if processed:
            return processed
    except Exception:
        _logger.debug("company_smart_theme: image_process failed", exc_info=True)

    if image_data[:4] == b"RIFF" and image_data[8:15] == b"WEBPVP8":
        try:
            img = Image.open(BytesIO(image_data)).convert("RGBA")
            out = BytesIO()
            img.save(out, format="PNG")
            return out.getvalue()
        except Exception:
            _logger.debug("company_smart_theme: WEBP conversion failed", exc_info=True)

    return image_data


def _extract_colors_from_svg(image_data):
    """Parse common SVG color attributes when raster extraction is unavailable."""
    try:
        text = image_data.decode("utf-8", errors="ignore")
    except Exception:
        return []

    if "<svg" not in text.lower():
        return []

    colors = []
    for match in SVG_COLOR_RE.finditer(text):
        if match.group(1):
            normalized = _normalize_hex(match.group(1))
            if normalized:
                colors.append(normalized)
        elif match.group(2):
            colors.append(_rgb_to_hex(match.group(2), match.group(3), match.group(4)))

    if not colors:
        for hex_color in HEX_COLOR_RE.findall(text):
            normalized = _normalize_hex(hex_color)
            if normalized:
                colors.append(normalized)

    # Drop white/near-white and transparent defaults.
    filtered = []
    for color in colors:
        r, g, b = _hex_to_rgb(color)
        if r > 240 and g > 240 and b > 240:
            continue
        if color.lower() in ("#000", "#000000", "#fff", "#ffffff"):
            continue
        filtered.append(color)

    # Preserve order but drop duplicates.
    seen = set()
    unique = []
    for color in filtered:
        if color not in seen:
            seen.add(color)
            unique.append(color)
    return unique


def _hex_to_rgb(hex_color):
    hex_color = (hex_color or "").lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def extract_dominant_color(image_bytes):
    """Extract a single dominant hex color from raw image bytes."""
    try:
        img = Image.open(BytesIO(image_bytes)).convert("RGBA")
        img.thumbnail((100, 100))
        pixels = list(img.getdata())

        filtered = [
            (r, g, b)
            for r, g, b, a in pixels
            if a > 50 and not (r > 240 and g > 240 and b > 240)
        ]
        if not filtered:
            return "#2c3e50"

        dominant = Counter(filtered).most_common(1)[0][0]
        return "#%02x%02x%02x" % dominant
    except Exception:
        return "#2c3e50"


def _brand_color_score(hex_color):
    """Prefer saturated mid-tone colors suitable for a navbar."""
    try:
        r, g, b = _hex_to_rgb(hex_color)
    except (ValueError, TypeError):
        return -1

    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    if lum < 0.12 or lum > 0.92:
        return -1

    max_c = max(r, g, b)
    min_c = min(r, g, b)
    saturation = (max_c - min_c) / max_c if max_c else 0
    if saturation < 0.08:
        return lum * 0.25
    return saturation * (1 - abs(lum - 0.42))


def pick_brand_color(palette_hex):
    """Pick the best navbar color from an extracted palette."""
    if not palette_hex:
        return DEFAULT_THEME_COLOR

    scored = [
        (color, _brand_color_score(color))
        for color in palette_hex
    ]
    viable = [item for item in scored if item[1] >= 0]
    if viable:
        return max(viable, key=lambda item: item[1])[0]
    return palette_hex[0]


def mix_with_white(hex_color, white_ratio=0.78):
    """Blend a hex color with white to produce a soft background tint."""
    try:
        r, g, b = _hex_to_rgb(hex_color)
    except (ValueError, TypeError):
        return "#f5f7fa"
    ratio = max(0.0, min(1.0, white_ratio))
    return _rgb_to_hex(
        int(r + (255 - r) * ratio),
        int(g + (255 - g) * ratio),
        int(b + (255 - b) * ratio),
    )


def pick_light_theme_color(base_color, palette_hex):
    """Return a visible light tone for form/background areas."""
    light_candidates = []
    for color in palette_hex:
        try:
            r, g, b = _hex_to_rgb(color)
        except (ValueError, TypeError):
            continue
        lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        max_c = max(r, g, b)
        min_c = min(r, g, b)
        saturation = (max_c - min_c) / max_c if max_c else 0
        if 0.35 <= lum <= 0.82 and saturation >= 0.12:
            light_candidates.append((color, lum, saturation))

    if light_candidates:
        # Prefer a clearly visible tint, not washed-out white.
        return min(light_candidates, key=lambda item: abs(item[1] - 0.58))[0]
    return mix_with_white(base_color, 0.72)


class ResCompany(models.Model):
    """Store company theme color and palette derived from the logo."""

    _inherit = "res.company"

    theme_color = fields.Char("Theme Color", default=DEFAULT_THEME_COLOR)
    auto_theme_from_logo = fields.Boolean("Auto Theme from Logo", default=True)
    theme_palette = fields.Text("Theme Palette")

    @api.model
    def _extract_colors_from_logo(self, logo, color_count=6):
        """
        Build a palette from the company logo using ColorThief with a PIL fallback.

        Returns:
            tuple[str, list[str]]: Main color and palette hex values.
        """
        if not logo:
            return DEFAULT_THEME_COLOR, list(FALLBACK_PALETTE)

        image_data = _decode_logo_bytes(logo)
        if not image_data:
            _logger.warning("company_smart_theme: invalid logo payload on company extraction")
            return DEFAULT_THEME_COLOR, list(FALLBACK_PALETTE)

        svg_palette = _extract_colors_from_svg(image_data)
        if svg_palette:
            main_color = pick_brand_color(svg_palette)
            return main_color, svg_palette[:6]

        raster_data = _normalize_logo_raster(image_data)
        if not raster_data:
            raster_data = image_data

        palette_hex = []
        if ColorThief is not None and raster_data:
            try:
                image = BytesIO(raster_data)
                color_thief = ColorThief(image)
                palette = color_thief.get_palette(color_count=color_count)
                palette_hex = ["#%02x%02x%02x" % c for c in palette if c]
            except Exception:
                _logger.debug(
                    "company_smart_theme: ColorThief failed, using PIL fallback",
                    exc_info=True,
                )

        if not palette_hex:
            main_color = extract_dominant_color(raster_data or image_data)
            palette_hex = [main_color]
        else:
            main_color = pick_brand_color(palette_hex)

        return main_color, palette_hex

    def _theme_palette_list(self):
        self.ensure_one()
        if not self.theme_palette:
            return []
        return [color.strip() for color in self.theme_palette.split(",") if color.strip()]

    def _theme_needs_sync(self):
        """True when auto mode is on but stored colors still look like defaults."""
        self.ensure_one()
        if not self.auto_theme_from_logo or not self.logo:
            return False
        palette = self._theme_palette_list()
        if not palette:
            return True
        if palette == list(FALLBACK_PALETTE):
            return True
        stored_color = (self.theme_color or "").upper()
        if stored_color == DEFAULT_THEME_COLOR.upper() and palette[0].upper() != DEFAULT_THEME_COLOR.upper():
            return True
        extracted_color, _palette = self._extract_colors_from_logo(self.logo)
        if extracted_color.upper() != stored_color and stored_color in (
            DEFAULT_THEME_COLOR.upper(),
            "#2C3E50",
        ):
            return True
        return False

    def _sync_theme_from_logo(self):
        """Persist theme_color and theme_palette from the current logo."""
        for company in self:
            if not company.auto_theme_from_logo or not company.logo:
                continue
            main_color, palette = company._extract_colors_from_logo(company.logo)
            company.with_context(company_smart_theme_skip_sync=True).write({
                "theme_color": main_color,
                "theme_palette": ",".join(palette),
            })

    def action_refresh_theme_from_logo(self):
        """Button on company form: re-extract palette from the logo."""
        self._sync_theme_from_logo()
        return True

    @api.model
    def action_refresh_all_themes_from_logo(self):
        """Upgrade hook: sync every company that uses auto theme from logo."""
        companies = self.search([
            ("auto_theme_from_logo", "=", True),
            ("logo", "!=", False),
        ])
        if companies:
            companies._sync_theme_from_logo()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        to_sync = records.filtered(lambda c: c.auto_theme_from_logo and c.logo)
        if to_sync:
            to_sync._sync_theme_from_logo()
        return records

    @api.onchange("logo", "auto_theme_from_logo")
    def _onchange_logo_theme(self):
        """Refresh theme preview fields when the logo changes in the form."""
        for company in self:
            if company.logo and company.auto_theme_from_logo:
                main_color, palette = company._extract_colors_from_logo(company.logo)
                company.theme_color = main_color
                company.theme_palette = ",".join(palette)

    def write(self, vals):
        """Persist logo-driven theme colors when auto mode is enabled."""
        if self.env.context.get("company_smart_theme_skip_sync"):
            return super().write(vals)

        res = super().write(vals)
        trigger_fields = {"logo", "auto_theme_from_logo", "partner_id"}
        if trigger_fields & set(vals):
            self.filtered(lambda c: c.auto_theme_from_logo and c.logo)._sync_theme_from_logo()
        return res

    @api.model
    def get_company_theme(self):
        """
        Return the active company's theme for the backend UI.

        Returns:
            dict: company_id, theme_color, and theme_palette list.
        """
        company = self.env.company.sudo()
        if company.auto_theme_from_logo and company.logo and company._theme_needs_sync():
            company._sync_theme_from_logo()
            company.invalidate_recordset(["theme_color", "theme_palette"])

        theme_color = company.theme_color or DEFAULT_THEME_COLOR
        user = self.env.user.sudo(False)
        if getattr(user, "theme_color", None) and user.theme_color not in (False, "#2C3E50"):
            theme_color = user.theme_color

        palette = company._theme_palette_list()
        if not palette:
            palette = [theme_color]
        theme_color_light = pick_light_theme_color(theme_color, palette)
        return {
            "company_id": company.id,
            "theme_color": theme_color,
            "theme_color_light": theme_color_light,
            "theme_palette": palette,
        }
