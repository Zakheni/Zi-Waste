"""Module lifecycle hooks for company_smart_theme."""


def post_init_hook(env):
    """Re-sync logo palettes for companies that still have default theme colors."""
    companies = env["res.company"].search([
        ("auto_theme_from_logo", "=", True),
        ("logo", "!=", False),
    ])
    for company in companies:
        if company._theme_needs_sync():
            company._sync_theme_from_logo()
