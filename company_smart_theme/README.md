Company Smart Theme (Odoo 17)
===================================

What it does
- Extracts a dominant color from company logo (auto_theme_color).
- Lets companies choose to use auto color or specify a manual theme_color.
- Lets users optionally override with a personal theme_color.
- Dynamically injects a per-session CSS file (/web/dynamic_theme.css) so backend navbar matches the chosen color.

Requirements
- Pillow must be installed in the Odoo Python environment: pip install Pillow
- Restart Odoo after installing the module.

Install
1. Unzip into your addons directory.
2. Restart Odoo server.
3. Update apps list and install 'Company Smart Theme' module.
4. Set company logo in Settings -> Companies -> select company -> Backend Theme tab (color computed automatically).
5. Optionally toggle Use Auto Theme Color or set Manual Theme Color. Users can set personal Theme Color in their Preferences.
6. Clear browser cache and reload backend.

Debug tips
- Open /web/dynamic_theme.css (while logged in) — it should return CSS with your color.
- If you see the red JS error banner, open browser DevTools Console for precise error.
