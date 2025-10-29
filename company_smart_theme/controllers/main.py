from odoo import http
from odoo.http import request
import colorsys

class DynamicThemeController(http.Controller):

    @http.route('/web/dynamic_theme.css', type='http', auth='user')
    def dynamic_theme_css(self):
        # Always fetch active company (multi-company safe)
        company = request.env.company
        base_color = company.theme_color or "#4CAF50"  # fallback green
        text_color = "#ffffff"

        # Helper: adjust hover shade from base color
        def adjust_color(hex_color, factor=0.85):
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            h, l, s = colorsys.rgb_to_hls(r/255, g/255, b/255)
            l = max(0, min(1, l * factor))
            r, g, b = colorsys.hls_to_rgb(h, l, s)
            return f'#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}'

        hover_color = adjust_color(base_color, 0.7)

        css = f"""
        :root {{
            --company-theme-color: {base_color};
            --company-theme-hover: {hover_color};
            --company-theme-text: {text_color};
        }}

        /* Navbar */
        .o_main_navbar {{
            background-color: var(--company-theme-color) !important;
            color: var(--company-theme-text) !important;
        }}

        /* Navbar sections */
        .o_main_navbar .o_menu_sections {{
            background-color: var(--company-theme-color) !important;
            color: var(--company-theme-text) !important;
        }}

        /* Navbar dropdowns */
        .o_main_navbar .o-dropdown,
        .o_main_navbar .o-dropdown .dropdown-toggle,
        .o_main_navbar .o-dropdown .dropdown-menu {{
            background-color: var(--company-theme-color) !important;
            color: var(--company-theme-text) !important;
        }}

        /* Dropdown entries */
        .dropdown-item,
        .o_nav_entry {{
            background-color: var(--company-theme-color) !important;
            color: var(--company-theme-text) !important;
        }}

        /* Sidebar */
        .o_main_sidebar {{
            background-color: var(--company-theme-color) !important;
        }}

        /* Sidebar apps and menu entries */
        .o_main_sidebar .o_app,
        .o_main_sidebar .o_menu_entry {{
            background-color: var(--company-theme-color) !important;
            color: var(--company-theme-text) !important;
        }}

        /* Hover state */
        .o_main_sidebar .o_app:hover,
        .o_main_sidebar .o_menu_entry:hover,
        .o_main_navbar .o-dropdown:hover,
        .o_main_navbar .o-dropdown .dropdown-menu .dropdown-item:hover,
        .o_main_navbar .o_menu_sections:hover,
        .dropdown-item:hover,
        .o_nav_entry:hover {{
            background-color: var(--company-theme-hover) !important;
            color: var(--company-theme-text) !important;
        }}
        """
        return request.make_response(css, [('Content-Type', 'text/css')])

    @http.route('/get_theme_color', type='json', auth='user')
    def get_theme_color(self):
        company = request.env.user.company_id
        return {'color': company.theme_color or "#2C3E50"}

    @http.route('/set_theme_color', type='json', auth='user')
    def set_theme_color(self, color):
        request.env.user.company_id.sudo().theme_color = color
        return {'status': 'ok'}