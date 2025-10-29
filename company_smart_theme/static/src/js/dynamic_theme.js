/** @odoo-module **/

import { jsonrpc } from "@web/core/network/rpc_service";

(function () {
    'use strict';

    let lastCompanyId = null;
    let lastThemeColor = null;
    const POLL_INTERVAL = 1500; // ms

    function applyTheme(base_color, hover_color, text_color) {
        try {
            let existing = document.getElementById("company-dynamic-theme");
            if (existing) {
                existing.parentNode.removeChild(existing);
            }
          const css = `
                :root {
                    --company-theme-color: ${base_color};
                    --company-theme-hover: ${hover_color};
                    --company-theme-text: ${text_color};
                }

                /* Navbar */
                .o_main_navbar {
                    background-color: var(--company-theme-color) !important;
                    color: var(--company-theme-text) !important;
                    border-color: var(--company-theme-color) !important;

                }

                /* Navbar sections */
                .o_main_navbar .o_menu_sections {
                    background-color: var(--company-theme-color) !important;
                    color: var(--company-theme-text) !important;
                }

                /* Navbar dropdowns */
                .o_main_navbar .o-dropdown,
                .o_main_navbar .o-dropdown .dropdown-toggle,
                .o_main_navbar .o-dropdown .dropdown-menu {
                    background-color: var(--company-theme-color) !important;
                    color: var(--company-theme-text) !important;
                }

                /* Dropdown entries */
                .dropdown-item,
                .o_nav_entry {
                    background-color: var(--company-theme-color) !important;
                    color: var(--company-theme-text) !important;
                }

                /* Sidebar */
                .o_main_sidebar {
                    background-color: var(--company-theme-color) !important;
                }

                /* Sidebar apps and menu entries */
                .o_main_sidebar .o_app,
                .o_main_sidebar .o_menu_entry {
                    background-color: var(--company-theme-color) !important;
                    color: var(--company-theme-text) !important;
                }

                /* Hover state */
                .o_main_sidebar .o_app:hover,
                .o_main_sidebar .o_menu_entry:hover,
                .o_main_navbar .o-dropdown:hover,
                .o_main_navbar .o-dropdown .dropdown-menu .dropdown-item:hover,
                .o_main_navbar .o_menu_sections:hover,
                .dropdown-item:hover,
                .o_nav_entry:hover {
                    background-color: var(--company-theme-color) !important;
                    color: var(--company-theme-text) !important;
                }

                /* Primary buttons */
                .btn-primary {
                    background-color: var(--company-theme-color) !important;
                    border-color: var(--company-theme-color) !important;
                    color: #fff !important;
                }

                .btn-primary:hover,
                .btn-primary:focus,
                .btn-primary:active {
                    background-color: var(--company-theme-hover) !important;
                    border-color: var(--company-theme-hover) !important;
                    color: #fff !important;
                }

                .btn-outline-primary,
                .btn-outline-primary:focus,
                .btn-outline-primary:active {
                    background-color: var(--company-theme-color) !important;
                    border-color: var(--company-theme-text) !important;
                    color: #fff !important;
                }

                 .btn-link {
                    color: var(--company-theme-color) !important;

                }
                .form-check-input {
                   background-color: var(--company-theme-color) !important;
                   border-color: var(--company-theme-color) !important;

                }

                 .text-bg-primary {
                   background-color: var(--company-theme-color) !important;

                }

                 .o_doc_link {
                   color: var(--company-theme-color) !important;

                }
                 .fa-lg {
                   color: var(--company-theme-color) !important;

                }
                .fa-folder{
                   color: var(--company-theme-color) !important;

                }
                .o_button_icon{
                   color: var(--company-theme-color) !important;

                }
                 .o_navbar {
                   background-color: var(--company-theme-color) !important;
                   border-color: var(--company-theme-color) !important;


                }

                .o_add_custom_group_menu .dropdown-item:focus {
                   background-color: var(--company-theme-color) !important;
                   border-color: var(--company-theme-color) !important;


                }
                /* Secondary buttons */
//                .btn-secondary {
//                    background-color: #fff !important;
//                    border: 1px solid var(--company-theme-color) !important;
//                    color: var(--company-theme-color) !important;
//                }

                .btn-secondary:hover,
                .btn-secondary:focus,
                .btn-secondary:active {
                    background-color: var(--company-theme-hover) !important;
                    border-color: var(--company-theme-hover) !important;
                    color: #fff !important;
                }
            `;

            const style = document.createElement("style");
            style.id = "company-dynamic-theme";
            style.type = "text/css";
            style.appendChild(document.createTextNode(css));
            document.head.appendChild(style);
        } catch (e) {
            console.error("company_smart_theme.applyTheme error:", e);
        }
    }

    // small helper to compute hover variant (darker) in JS if server didn't return one
    function darkenHex(hex, factor = 0.75) {
        try {
            hex = hex.replace('#', '');
            let r = parseInt(hex.substring(0, 2), 16);
            let g = parseInt(hex.substring(2, 4), 16);
            let b = parseInt(hex.substring(4, 6), 16);
            r = Math.max(0, Math.min(255, Math.floor(r * factor)));
            g = Math.max(0, Math.min(255, Math.floor(g * factor)));
            b = Math.max(0, Math.min(255, Math.floor(b * factor)));
            return '#' + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
        } catch (e) {
            return hex;
        }
    }

    // render swatches (click saves selected color to company.theme_color via rpc write)
    function renderSwatches(palette, company_id) {
        try {
            // remove old container
            let old = document.getElementById("theme-swatches");
            if (old) old.remove();

            if (!palette || !palette.length) return;

            const nav = document.querySelector(".o_main_navbar");
            if (!nav) return;

            const container = document.createElement("div");
            container.id = "theme-swatches";
            container.style.display = "flex";
            container.style.gap = "6px";
            container.style.alignItems = "center";
            container.style.marginLeft = "10px";
            container.style.marginRight = "10px";

            palette.forEach((color) => {
                const sw = document.createElement("div");
                sw.style.width = "18px";
                sw.style.height = "18px";
                sw.style.borderRadius = "50%";
                sw.style.cursor = "pointer";
                sw.style.border = "1px solid rgba(255,255,255,0.6)";
                sw.style.backgroundColor = color;
                sw.title = `Use ${color}`;
                sw.onclick = async function () {
                    try {
                        // write to company record (requires user to have rights)
                        await jsonrpc("/web/dataset/call_kw/res.company/write", {
                            model: "res.company",
                            method: "write",
                            args: [[company_id], { theme_color: color }],
                            kwargs: {},
                        });
                        // apply chosen color immediately
                        applyTheme(color, darkenHex(color, 0.75), "#ffffff");
                    } catch (err) {
                        console.error("Failed to save selected theme color:", err);
                        alert("Unable to save palette color — you might not have rights to change company settings.");
                    }
                };
                container.appendChild(sw);
            });

            // append to navbar (on the right of apps)
            nav.appendChild(container);
        } catch (e) {
            console.error("company_smart_theme.renderSwatches error:", e);
        }
    }

    async function checkAndUpdateTheme() {
        try {
            const result = await jsonrpc("/web/dataset/call_kw/res.company/get_company_theme", {
                model: "res.company",
                method: "get_company_theme",
                args: [],
                kwargs: {},
            });
            if (!result) return;

            const company_id = result.company_id;
            const theme_color = result.theme_color || "#4CAF50";
            const palette = result.theme_palette || [];
            const hover_color = (palette && palette[1]) ? palette[1] : darkenHex(theme_color, 0.75);

            // if company changed or color changed, reapply
            if (company_id !== lastCompanyId || theme_color !== lastThemeColor) {
                lastCompanyId = company_id;
                lastThemeColor = theme_color;
                applyTheme(theme_color, hover_color, "#ffffff");
                renderSwatches(palette, company_id);
            }
        } catch (e) {
            // ignore transient failures, but log once
            console.error("company_smart_theme.checkAndUpdateTheme error:", e);
        }
    }

    // initial load + polling
    function init() {
        checkAndUpdateTheme();
        // Polling keeps theme in sync when user switches company; Odoo may reload the page on switch,
        // but this ensures we catch the change even if the client doesn't fully reload.
        setInterval(checkAndUpdateTheme, POLL_INTERVAL);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();




//import { jsonrpc } from "@web/core/network/rpc_service";
//
//(function () {
//    'use strict';
//
//    function applyCompanyTheme() {
//        jsonrpc("/web/dataset/call_kw/res.company/get_company_theme", {
//            model: "res.company",
//            method: "get_company_theme",
//            args: [],
//            kwargs: {},
//        }).then((result) => {
//            try {
//                // Remove existing style if any
//                var existing = document.getElementById('company-dynamic-theme');
//                if (existing) {
//                    existing.parentNode.removeChild(existing);
//                }
//
//                // Inject new <style> with dynamic colors
//                var style = document.createElement('style');
//                style.id = 'company-dynamic-theme';
//                style.type = 'text/css';
//                style.innerHTML = `
//                    :root {
//                        --company-theme-color: ${result.theme_color};
//                    }
//
//                    /* Main navbar + sidebar */
//                    .o_main_navbar,
//                    .o_main_sidebar {
//                        background-color: var(--company-theme-color) !important;
//                    }
//
//                    /* Menu dropdown hover + sections */
//                    .o_menu_sections .o-dropdown .dropdown-menu,
//                    .dropdown-item.o_nav_entry:hover {
//                        background-color: var(--company-theme-color) !important;
//                        color: #fff !important;
//                    }
//
//                    /* Menu entries text/icons */
//                    .o_menu_systray .dropdown-toggle,
//                    .o_main_sidebar .o_app,
//                    .o_main_sidebar .o_menu_entry {
//                        color: #fff !important;
//                    }
//                     /* Navbar dropdowns */
//                    .o_main_navbar .o-dropdown,
//                    .o_main_navbar .o-dropdown .dropdown-toggle,
//                    .o_main_navbar .o-dropdown .dropdown-menu {{
//                        background-color: var(--company-theme-color) !important;
//                        color: var(--company-theme-text) !important;
//                    }}
//                `;
//                document.head.appendChild(style);
//
//                // (Optional) Show palette in console
//                console.log("Available palette colors:", result.theme_palette);
//
//            } catch (err) {
//                console.error('company_smart_theme: failed to inject dynamic CSS', err);
//            }
//        });
//    }
//
//    if (document.readyState === 'loading') {
//        document.addEventListener('DOMContentLoaded', applyCompanyTheme);
//    } else {
//        applyCompanyTheme();
//    }
//})();


//(function () {
//    'use strict';
//
//    function loadDynamicTheme() {
//        try {
//            var existing = document.getElementById('company-dynamic-theme');
//            if (existing) {
//                existing.parentNode.removeChild(existing);
//            }
//            var link = document.createElement('link');
//            link.id = 'company-dynamic-theme';
//            link.rel = 'stylesheet';
//            link.type = 'text/css';
//            link.href = '/web/dynamic_theme.css?cache=' + Date.now();
//            document.getElementsByTagName('head')[0].appendChild(link);
//        } catch (err) {
//            console.error('company_smart_theme: failed to inject dynamic CSS', err);
//        }
//    }
//
//    if (document.readyState === 'loading') {
//        document.addEventListener('DOMContentLoaded', loadDynamicTheme);
//    } else {
//        loadDynamicTheme();
//    }
//})();
