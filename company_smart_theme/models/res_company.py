import base64
from io import BytesIO
from collections import Counter
from PIL import Image
from odoo import api, fields, models
from colorthief import ColorThief


def extract_dominant_color(image_bytes):
    """Extract a dominant color from an image (returns hex)."""
    try:
        img = Image.open(BytesIO(image_bytes)).convert('RGBA')
        img.thumbnail((100, 100))
        pixels = list(img.getdata())

        # Filter transparent + white
        filtered = [
            (r, g, b) for r, g, b, a in pixels
            if a > 50 and not (r > 240 and g > 240 and b > 240)
        ]
        if not filtered:
            return '#2c3e50'

        dominant = Counter(filtered).most_common(1)[0][0]
        return '#%02x%02x%02x' % dominant
    except Exception:
        return '#2c3e50'


class ResCompany(models.Model):
    _inherit = "res.company"

    theme_color = fields.Char("Theme Color", default="#4CAF50")
    auto_theme_from_logo = fields.Boolean("Auto Theme from Logo", default=True)
    theme_palette = fields.Text("Theme Palette")  # store multiple colors as comma-separated

    # -------------------
    # COLOR EXTRACTION
    # -------------------
    @api.model
    def _extract_colors_from_logo(self, logo, color_count=6):
        """Extract palette colors from logo using ColorThief."""
        try:
            image_data = base64.b64decode(logo)
            image = BytesIO(image_data)
            color_thief = ColorThief(image)

            # Palette colors
            palette = color_thief.get_palette(color_count=color_count)
            palette_hex = ['#%02x%02x%02x' % c for c in palette]

            # First palette color = main theme color
            main_color = palette_hex[0] if palette_hex else "#4CAF50"

            return main_color, palette_hex
        except Exception:
            # fallback palette
            fallback_palette = ["#4CAF50", "#388E3C", "#81C784", "#A5D6A7"]
            return fallback_palette[0], fallback_palette

    # -------------------
    # ONCHANGE (UI Only)
    # -------------------
    @api.onchange("logo", "auto_theme_from_logo")
    def _onchange_logo_theme(self):
        """Update theme color + palette in UI when logo changes or auto mode is on."""
        for company in self:
            if company.logo and company.auto_theme_from_logo:
                main_color, palette = company._extract_colors_from_logo(company.logo)
                company.theme_color = main_color
                company.theme_palette = ",".join(palette)

    # -------------------
    # OVERRIDE WRITE (DB)
    # -------------------
    def write(self, vals):
        """Ensure theme color updates automatically on logo update."""
        res = super().write(vals)
        for company in self:
            if company.logo and company.auto_theme_from_logo and ("logo" in vals or "auto_theme_from_logo" in vals):
                main_color, palette = company._extract_colors_from_logo(company.logo)
                company.sudo().write({
                    "theme_color": main_color,  # <-- first color from palette
                    "theme_palette": ",".join(palette),
                })
        return res

    # -------------------
    # PUBLIC GETTER
    # -------------------
    @api.model
    def get_company_theme(self):
        """Return active company's theme (main color + palette)."""
        company = self.env.company
        return {
            "theme_color": company.theme_color,
            "theme_palette": company.theme_palette.split(",") if company.theme_palette else [],
        }

class ResUsers(models.Model):
    _inherit = "res.users"

    class ResUsers(models.Model):
        _inherit = "res.users"

        theme_color = fields.Char(string="Theme Color", default="#2C3E50")



# import base64
# from io import BytesIO
# from collections import Counter
# from PIL import Image
# from odoo import api, fields, models
# from colorthief import ColorThief
#
#
# def extract_dominant_color(image_bytes):
#     """Extract a dominant color from an image (returns hex)."""
#     try:
#         img = Image.open(BytesIO(image_bytes)).convert('RGBA')
#         img.thumbnail((100, 100))
#         pixels = list(img.getdata())
#
#         # Filter transparent + white
#         filtered = [
#             (r, g, b) for r, g, b, a in pixels
#             if a > 50 and not (r > 240 and g > 240 and b > 240)
#         ]
#         if not filtered:
#             return '#2c3e50'
#
#         dominant = Counter(filtered).most_common(1)[0][0]
#         return '#%02x%02x%02x' % dominant
#     except Exception:
#         return '#2c3e50'
#
#
# class ResCompany(models.Model):
#     _inherit = "res.company"
#
#     # theme_color = fields.Char("Theme Color", default="#4CAF50")
#     # auto_theme_from_logo = fields.Boolean("Auto Theme from Logo", default=True)
#     #
#     # @api.model
#     # def _extract_color_from_logo(self, logo):
#     #     """Extract dominant color from logo using ColorThief."""
#     #     try:
#     #         image_data = base64.b64decode(logo)
#     #         image = BytesIO(image_data)
#     #         color_thief = ColorThief(image)
#     #         dominant_color = color_thief.get_color(quality=1)
#     #         return '#%02x%02x%02x' % dominant_color
#     #     except Exception:
#     #         return "#4CAF50"  # fallback default green
#     #
#     # @api.onchange("logo", "auto_theme_from_logo")
#     # def _onchange_logo_theme(self):
#     #     """Update theme color when logo changes or option toggled."""
#     #     for company in self:
#     #         if company.logo and company.auto_theme_from_logo:
#     #             company.theme_color = self._extract_color_from_logo(company.logo)
#     # theme_color = fields.Char("Theme Color", default="#4CAF50")
#     # auto_theme_from_logo = fields.Boolean("Auto Theme from Logo", default=True)
#     #
#     # @api.model
#     # def _extract_color_from_logo(self, logo):
#     #     """Extract main (vibrant) color from the logo using ColorThief palette."""
#     #     try:
#     #         image_data = base64.b64decode(logo)
#     #         image = BytesIO(image_data)
#     #         color_thief = ColorThief(image)
#     #
#     #         # Get a palette of up to 6 colors
#     #         palette = color_thief.get_palette(color_count=6, quality=1)
#     #         if not palette:
#     #             return "#4CAF50"
#     #
#     #         # Pick the most saturated (vibrant) color
#     #         def saturation(rgb):
#     #             r, g, b = [x / 255.0 for x in rgb]
#     #             maxc, minc = max(r, g, b), min(r, g, b)
#     #             return 0 if maxc == minc else (maxc - minc) / maxc
#     #
#     #         vibrant_color = max(palette, key=saturation)
#     #         return '#%02x%02x%02x' % vibrant_color
#     #
#     #     except Exception:
#     #         return "#4CAF50"  # fallback green
#     #
#     # @api.onchange("logo", "auto_theme_from_logo")
#     # def _onchange_logo_theme(self):
#     #     """Update theme color when logo changes or option toggled."""
#     #     for company in self:
#     #         if company.logo and company.auto_theme_from_logo:
#     #             company.theme_color = self._extract_color_from_logo(company.logo)
#
#     theme_color = fields.Char("Theme Color", default="#4CAF50")
#     auto_theme_from_logo = fields.Boolean("Auto Theme from Logo", default=True)
#     theme_palette = fields.Text("Theme Palette")  # will store multiple colors as JSON or comma-separated
#
#     @api.model
#     def _extract_colors_from_logo(self, logo, color_count=6):
#         """Extract dominant + palette colors from logo using ColorThief."""
#         try:
#             image_data = base64.b64decode(logo)
#             image = BytesIO(image_data)
#             color_thief = ColorThief(image)
#
#             # Dominant color
#             dominant_color = color_thief.get_color(quality=1)
#             main_color = '#%02x%02x%02x' % dominant_color
#
#             # Palette colors
#             palette = color_thief.get_palette(color_count=color_count)
#             palette_hex = ['#%02x%02x%02x' % c for c in palette]
#
#             return main_color, palette_hex
#         except Exception:
#             return "#4CAF50", ["#4CAF50", "#388E3C", "#81C784", "#A5D6A7"]
#
#     @api.onchange("logo", "auto_theme_from_logo")
#     def _onchange_logo_theme(self):
#         """Update theme color + palette when logo changes or auto mode is on."""
#         for company in self:
#             if company.logo and company.auto_theme_from_logo:
#                 main_color, palette = self._extract_colors_from_logo(company.logo)
#                 company.theme_color = main_color
#                 company.theme_palette = ",".join(palette)
#
#     @api.model
#     def get_company_theme(self):
#         """Return active company's theme (main color + palette)."""
#         company = self.env.company
#         return {
#             "theme_color": company.theme_color,
#             "theme_palette": company.theme_palette.split(",") if company.theme_palette else [],
#         }
#
#     # def write(self, vals):
#     #     """Ensure theme color updates automatically on logo update."""
#     #     res = super().write(vals)
#     #     for company in self:
#     #         if company.logo and company.auto_theme_from_logo and ("logo" in vals or "auto_theme_from_logo" in vals):
#     #             company.theme_color = company._extract_color_from_logo(company.logo)
#     #     return res
#
#     @api.depends("logo_web")
#     def _compute_auto_theme_color(self):
#         for company in self:
#             company.auto_theme_color = "#2c3e50"
#             if not company.logo_web:
#                 continue
#             try:
#                 image_bytes = base64.b64decode(company.logo_web)
#                 company.auto_theme_color = extract_dominant_color(image_bytes)
#             except Exception:
#                 company.auto_theme_color = "#2c3e50"
#
#
# class ResUsers(models.Model):
#     _inherit = "res.users"
#
#     class ResUsers(models.Model):
#         _inherit = "res.users"
#
#         theme_color = fields.Char(string="Theme Color", default="#2C3E50")
#
