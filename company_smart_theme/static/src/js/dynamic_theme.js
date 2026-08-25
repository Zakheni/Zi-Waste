/** @odoo-module **/
/**
 * Polished company theme: strong navbar brand color, clean white forms,
 * subtle tinted page background, brand accents only.
 */

import { registry } from "@web/core/registry";
import { cookie } from "@web/core/browser/cookie";
import { DARK_MODE_ENABLED } from "./theme_config";

const STYLE_ID = "company-dynamic-theme";
const POLL_MS = 5000;
const DEFAULT_COLOR = "#4CAF50";

function parseHex(hex) {
    hex = (hex || DEFAULT_COLOR).replace("#", "");
    if (hex.length === 3) {
        hex = hex
            .split("")
            .map((c) => c + c)
            .join("");
    }
    return {
        r: parseInt(hex.substring(0, 2), 16),
        g: parseInt(hex.substring(2, 4), 16),
        b: parseInt(hex.substring(4, 6), 16),
    };
}

function toHex(r, g, b) {
    return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
}

function relativeLuminance(hex) {
    const { r, g, b } = parseHex(hex);
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255;
}

function contrastNavText(hex) {
    return relativeLuminance(hex) > 0.55 ? "#1f2937" : "#ffffff";
}

function navIconColor(hex) {
    return relativeLuminance(hex) > 0.55 ? darkenHex(hex, 0.48) : "#ffffff";
}

function darkenHex(hex, factor = 0.82) {
    try {
        const { r, g, b } = parseHex(hex);
        return toHex(
            Math.max(0, Math.min(255, Math.floor(r * factor))),
            Math.max(0, Math.min(255, Math.floor(g * factor))),
            Math.max(0, Math.min(255, Math.floor(b * factor)))
        );
    } catch (_e) {
        return hex;
    }
}

function mixWithWhite(hex, whiteRatio = 0.92) {
    try {
        const { r, g, b } = parseHex(hex);
        const ratio = Math.max(0, Math.min(1, whiteRatio));
        return toHex(
            Math.round(r + (255 - r) * ratio),
            Math.round(g + (255 - g) * ratio),
            Math.round(b + (255 - b) * ratio)
        );
    } catch (_e) {
        return "#f4f6f8";
    }
}

function rgbaFromHex(hex, alpha) {
    const { r, g, b } = parseHex(hex);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function mixWithBlack(hex, blackRatio = 0.85) {
    try {
        const { r, g, b } = parseHex(hex);
        const ratio = Math.max(0, Math.min(1, blackRatio));
        return toHex(
            Math.round(r * (1 - ratio)),
            Math.round(g * (1 - ratio)),
            Math.round(b * (1 - ratio))
        );
    } catch (_e) {
        return "#121212";
    }
}

function isDarkMode() {
    return DARK_MODE_ENABLED && cookie.get("color_scheme") === "dark";
}

function navbarHoverOverlay(hex) {
    return relativeLuminance(hex) > 0.55 ? "rgba(0, 0, 0, 0.06)" : "rgba(255, 255, 255, 0.14)";
}

function navbarActiveOverlay(hex) {
    return relativeLuminance(hex) > 0.55 ? "rgba(0, 0, 0, 0.1)" : "rgba(255, 255, 255, 0.2)";
}

function buildThemeCss(baseColor, isDark = isDarkMode()) {
    const navText = contrastNavText(baseColor);
    const iconColor = navIconColor(baseColor);
    const borderColor = darkenHex(baseColor, 0.78);
    const hoverOverlay = navbarHoverOverlay(baseColor);
    const activeOverlay = navbarActiveOverlay(baseColor);
    const pageBg = isDark ? mixWithBlack(baseColor, 0.91) : mixWithWhite(baseColor, 0.93);
    const formSurround = isDark ? mixWithBlack(baseColor, 0.86) : mixWithWhite(baseColor, 0.88);
    const formSheet = isDark ? mixWithBlack(baseColor, 0.78) : "#ffffff";
    const formSheetText = isDark ? "#e5e7eb" : "#374151";
    const controlPanelBg = isDark ? mixWithBlack(baseColor, 0.82) : "#ffffff";
    const statusStepBg = isDark ? mixWithBlack(baseColor, 0.72) : mixWithWhite(baseColor, 0.76);
    const statusStepHover = isDark ? mixWithBlack(baseColor, 0.65) : mixWithWhite(baseColor, 0.68);
    const dropdownBg = isDark ? mixWithBlack(baseColor, 0.75) : mixWithWhite(baseColor, 0.90);
    const dropdownHover = isDark ? mixWithBlack(baseColor, 0.68) : mixWithWhite(baseColor, 0.80);
    const accentSoft = rgbaFromHex(baseColor, isDark ? 0.22 : 0.12);
    const inputBg = isDark ? mixWithBlack(baseColor, 0.70) : "#ffffff";
    const inputText = isDark ? "#f3f4f6" : "#1f2937";
    const inputBorder = isDark ? mixWithBlack(baseColor, 0.55) : "#d1d5db";
    const textMuted = isDark ? "#9ca3af" : "#6b7280";
    const textHeading = isDark ? "#f9fafb" : "#111827";
    const textLabel = isDark ? "#d1d5db" : "#4b5563";
    const textBody = isDark ? "#e5e7eb" : "#374151";
    const textHover = isDark ? "#f9fafb" : "#111827";
    const textSoft = isDark ? "#9ca3af" : "#4b5563";
    const btnOutlineBg = isDark ? mixWithBlack(baseColor, 0.78) : "#ffffff";
    const formShadow = isDark
        ? "0 2px 12px rgba(0, 0, 0, 0.35)"
        : "0 2px 12px rgba(0, 0, 0, 0.06)";
    const wmzSummaryBg = isDark
        ? `linear-gradient(90deg, ${mixWithBlack(baseColor, 0.72)} 0%, ${mixWithBlack(baseColor, 0.65)} 100%)`
        : `linear-gradient(90deg, ${mixWithWhite(baseColor, 0.96)} 0%, ${mixWithWhite(baseColor, 0.92)} 100%)`;
    const wmzSummaryBorder = isDark ? mixWithBlack(baseColor, 0.55) : mixWithWhite(baseColor, 0.82);
    const statAccent = isDark ? mixWithWhite(baseColor, 0.55) : baseColor;
    const statValueColor = isDark ? "#f3f4f6" : statAccent;
    const statLabelColor = isDark ? "#9ca3af" : textMuted;
    const statIconColor = isDark ? mixWithWhite(baseColor, 0.62) : statAccent;
    const statBtnBg = isDark ? mixWithBlack(baseColor, 0.74) : "#ffffff";
    const statBtnBorder = isDark ? mixWithBlack(baseColor, 0.52) : darkenHex(baseColor, 0.58);
    const statBtnHover = isDark ? mixWithBlack(baseColor, 0.66) : mixWithWhite(baseColor, 0.88);
    const chatterBg = isDark ? mixWithBlack(baseColor, 0.86) : mixWithWhite(baseColor, 0.88);
    const chatterTopbar = isDark ? mixWithBlack(baseColor, 0.82) : "#ffffff";
    const chatterBorder = isDark ? mixWithBlack(baseColor, 0.55) : mixWithWhite(baseColor, 0.80);
    const chatterBubbleIn = isDark ? mixWithBlack(baseColor, 0.72) : "rgba(59, 130, 246, 0.12)";
    const chatterBubbleInBorder = isDark ? mixWithBlack(baseColor, 0.58) : "rgba(59, 130, 246, 0.28)";
    const chatterBubbleOut = isDark ? mixWithBlack(baseColor, 0.70) : "rgba(34, 197, 94, 0.12)";
    const chatterBubbleOutBorder = isDark ? mixWithBlack(baseColor, 0.56) : "rgba(34, 197, 94, 0.28)";
    const listBg = isDark ? mixWithBlack(baseColor, 0.78) : "#ffffff";
    const listStripeBg = isDark ? rgbaFromHex("#ffffff", 0.04) : rgbaFromHex(baseColor, 0.04);
    const listHoverBg = isDark ? rgbaFromHex("#ffffff", 0.08) : rgbaFromHex(baseColor, 0.06);
    const listFocusBg = isDark ? rgbaFromHex("#ffffff", 0.06) : mixWithWhite(baseColor, 0.94);
    const listSelectedBg = isDark ? rgbaFromHex(baseColor, 0.28) : rgbaFromHex(baseColor, 0.10);
    const listHeaderBg = isDark ? mixWithBlack(baseColor, 0.82) : "#ffffff";
    const listBorder = isDark ? mixWithBlack(baseColor, 0.52) : "#dee2e6";
    const listText = textBody;
    const listHeaderText = textHeading;

    return `
        :root {
            --company-theme-color: ${baseColor};
            --company-theme-border: ${borderColor};
            --company-theme-page: ${pageBg};
            --company-theme-surround: ${formSurround};
            --company-theme-accent-soft: ${accentSoft};
            --company-theme-dropdown: ${dropdownBg};
            --company-stat-btn-bg: ${statBtnBg};
            --company-stat-btn-border: ${statBtnBorder};
            --company-stat-btn-hover: ${statBtnHover};
            --company-stat-btn-color: ${textBody};
            --company-stat-btn-hover-color: ${textHover};
            --company-stat-label: ${statLabelColor};
            --company-stat-value: ${statValueColor};
            --company-stat-icon: ${statIconColor};
            --o-stat-text-color: ${statValueColor};
            --o-stat-button-color: ${statIconColor};
            --wmz-summary-bg: ${wmzSummaryBg};
            --wmz-summary-border: ${wmzSummaryBorder};
            --wmz-summary-label: ${textMuted};
            --wmz-summary-value: ${textBody};
            --wmz-subtitle-color: ${textSoft};
            --wmz-alert-success-bg: ${isDark ? rgbaFromHex("#22c55e", 0.16) : "#d1fae5"};
            --wmz-alert-success-border: ${isDark ? rgbaFromHex("#22c55e", 0.42) : "#a7f3d0"};
            --wmz-alert-success-text: ${isDark ? "#bbf7d0" : "#065f46"};
            --wmz-alert-danger-bg: ${isDark ? rgbaFromHex("#ef4444", 0.16) : "#fee2e2"};
            --wmz-alert-danger-border: ${isDark ? rgbaFromHex("#ef4444", 0.42) : "#fecaca"};
            --wmz-alert-danger-text: ${isDark ? "#fecaca" : "#991b1b"};
            --wmz-alert-info-bg: ${isDark ? rgbaFromHex("#3b82f6", 0.16) : "#dbeafe"};
            --wmz-alert-info-border: ${isDark ? rgbaFromHex("#3b82f6", 0.42) : "#bfdbfe"};
            --wmz-alert-info-text: ${isDark ? "#bfdbfe" : "#1e40af"};
            --wmz-ribbon-success-bg: ${isDark ? "#15803d" : "#198754"};
            --wmz-ribbon-danger-bg: ${isDark ? "#b91c1c" : "#dc3545"};
            --company-chatter-bg: ${chatterBg};
            --company-chatter-topbar-bg: ${chatterTopbar};
            --company-chatter-border: ${chatterBorder};
            --company-chatter-text: ${textBody};
            --company-chatter-muted: ${textMuted};
            --company-chatter-btn-bg: ${isDark ? mixWithBlack(baseColor, 0.74) : "#f8f9fa"};
            --company-chatter-btn-border: ${inputBorder};
            --company-chatter-btn-color: ${textBody};
            --company-chatter-btn-hover: ${isDark ? mixWithBlack(baseColor, 0.68) : mixWithWhite(baseColor, 0.90)};
            --company-chatter-input-bg: ${inputBg};
            --company-chatter-input-border: ${inputBorder};
            --company-chatter-bubble-in: ${chatterBubbleIn};
            --company-chatter-bubble-in-border: ${chatterBubbleInBorder};
            --company-chatter-bubble-out: ${chatterBubbleOut};
            --company-chatter-bubble-out-border: ${chatterBubbleOutBorder};
            --company-list-bg: ${listBg};
            --company-list-stripe-bg: ${listStripeBg};
            --company-list-hover-bg: ${listHoverBg};
            --company-list-focus-bg: ${listFocusBg};
            --company-list-selected-bg: ${listSelectedBg};
            --company-list-header-bg: ${listHeaderBg};
            --company-list-border: ${listBorder};
            --company-list-text: ${listText};
            --company-list-header-text: ${listHeaderText};
            --o-brand-odoo: ${baseColor};
            --company-theme-hover: ${borderColor};
            --company-theme-text: ${navText};
            --bs-primary: ${baseColor};
            accent-color: ${baseColor};
            --NavBar-brand-color: ${navText};
            --NavBar-entry-color: ${navText};
            --NavBar-icon-color: ${iconColor};
            --NavBar-entry-color--hover: ${navText};
            --NavBar-entry-color--active: ${navText};
            --NavBar-entry-backgroundColor: transparent;
            --NavBar-entry-backgroundColor--hover: ${hoverOverlay};
            --NavBar-entry-backgroundColor--focus: ${hoverOverlay};
            --NavBar-entry-backgroundColor--active: ${activeOverlay};
        }

        /* ---- Navbar (brand) ---- */
        .o_main_navbar {
            background: ${baseColor} !important;
            border-bottom: 2px solid ${borderColor} !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
        }

        .o_main_navbar .o_nav_entry,
        .o_main_navbar .dropdown-toggle,
        .o_main_navbar .o_menu_brand {
            color: ${navText} !important;
        }

        .o_main_navbar .o_menu_sections .o_nav_entry:hover,
        .o_main_navbar .o_menu_sections .dropdown-toggle:hover,
        .o_main_navbar .o_navbar_apps_menu .dropdown-toggle:hover {
            background: ${hoverOverlay} !important;
            color: ${navText} !important;
        }

        .o_main_navbar .o_menu_sections .dropdown.show > .dropdown-toggle,
        .o_main_navbar .o_menu_sections .o_nav_entry:active,
        .o_main_navbar .o_menu_sections .dropdown-toggle:active {
            background: ${activeOverlay} !important;
            color: ${navText} !important;
        }

        /* ---- Navbar icons: dark brand shade on light bars, white on dark ---- */
        .o_main_navbar .fa,
        .o_main_navbar .oi,
        .o_main_navbar i[class*="fa-"],
        .o_main_navbar i[class*="oi-"],
        .o_main_navbar .o_navbar_apps_menu .dropdown-toggle,
        .o_main_navbar .o_navbar_apps_menu .dropdown-toggle .fa,
        .o_main_navbar .o_navbar_apps_menu .dropdown-toggle .oi,
        .o_main_navbar .o_menu_systray .dropdown-toggle,
        .o_main_navbar .o_menu_systray .dropdown-toggle .fa,
        .o_main_navbar .o_menu_systray .dropdown-toggle .oi,
        .o_main_navbar .o_menu_systray .dropdown-toggle i,
        .o_main_navbar .o-mail-DiscussSystray-class .dropdown-toggle i,
        .o_main_navbar .o_switch_company_menu .dropdown-toggle i,
        .o_main_navbar .o_user_menu .dropdown-toggle i,
        .o_main_navbar .o_dark_mode_toggle,
        .o_main_navbar .o_dark_mode_toggle i,
        .o_main_navbar .o_nav_entry .fa,
        .o_main_navbar .o_nav_entry .oi,
        .o_main_navbar .dropdown-toggle .fa,
        .o_main_navbar .dropdown-toggle .oi {
            color: var(--NavBar-icon-color, ${iconColor}) !important;
        }

        .o_main_navbar svg,
        .o_main_navbar svg path,
        .o_main_navbar svg use {
            fill: var(--NavBar-icon-color, ${iconColor}) !important;
            color: var(--NavBar-icon-color, ${iconColor}) !important;
        }

        .o_main_navbar .o_menu_systray .badge,
        .o_main_navbar .o-mail-MessagingMenu-counter,
        .o_main_navbar .o-mail-ActivityMenu-counter,
        .o_main_navbar .o-discuss-badge {
            color: #ffffff !important;
        }

        /* ---- Page & lists ---- */
        .o_web_client,
        .o_action_manager,
        .o_content,
        .o_list_view .o_list_renderer,
        .o_kanban_view {
            background-color: var(--company-theme-page) !important;
        }

        /* ---- List / tree views ---- */
        .o_list_view .o_list_renderer {
            --ListRenderer-thead-bg-color: ${listHeaderBg};
            --ListRenderer-thead-border-end-color: ${listBorder};
            --ListRenderer-tfoot-bg-color: ${listHeaderBg};
        }

        .o_list_view .o_list_table {
            --table-bg: ${listBg};
            --bs-table-bg: ${listBg};
            --bs-table-color: ${listText};
            --bs-table-striped-bg: ${listStripeBg};
            --bs-table-striped-color: ${listText};
            --bs-table-hover-bg: ${listHoverBg};
            --bs-table-hover-color: ${listText};
            --bs-table-active-bg: ${listSelectedBg};
            --bs-table-active-color: ${listText};
            border-color: ${listBorder} !important;
            color: ${listText};
        }

        .o_list_view .o_list_table thead th {
            color: ${listHeaderText} !important;
            border-color: ${listBorder} !important;
        }

        .o_list_view .o_list_table .o_data_row {
            border-color: ${listBorder} !important;
        }

        .o_list_view .o_list_table .o_data_cell,
        .o_list_view .o_list_table .o_data_cell .o_field_widget {
            color: ${listText};
        }

        .o_list_view .o_list_table.o_keyboard_navigation th:focus-within,
        .o_list_view .o_list_table.o_keyboard_navigation td:focus-within {
            --bs-table-accent-bg: transparent !important;
            background-color: ${listFocusBg} !important;
            color: ${listText} !important;
        }

        .o_list_view .o_list_table .o_selected_row th:focus-within,
        .o_list_view .o_list_table .o_selected_row td:focus-within {
            background-color: ${listBg} !important;
        }

        .o_list_view .o_list_table .o_data_row:not(.o_selected_row):not(.o_data_row_selected):focus-within > * {
            --bs-table-accent-bg: ${listHoverBg} !important;
        }

        .o_list_view .o_list_table.table-hover > tbody > tr:hover > * {
            --bs-table-accent-bg: ${listHoverBg} !important;
            color: ${listText} !important;
        }

        .o_list_view .o_list_table .o_data_row.o_data_row_selected > .o_data_cell {
            --bs-table-accent-bg: ${listSelectedBg} !important;
        }

        .o_list_view .o_list_table tbody > tr.o_group_header > th,
        .o_list_view .o_list_table tbody > tr.o_group_header > td {
            background-color: ${listHeaderBg} !important;
            color: ${listHeaderText} !important;
        }

        ${isDark ? `
        .o_list_view .o_list_table .text-success {
            color: #4ade80 !important;
        }

        .o_list_view .o_list_table .text-info {
            color: #60a5fa !important;
        }

        .o_list_view .o_list_table .text-warning {
            color: #fbbf24 !important;
        }

        .o_list_view .o_list_table .text-danger {
            color: #f87171 !important;
        }

        .o_list_view .o_list_table .o_field_badge .badge {
            opacity: 1;
        }
        ` : ""}

        .o_control_panel {
            background-color: ${controlPanelBg} !important;
            border-bottom: 1px solid ${formSurround} !important;
            color: ${textBody} !important;
        }

        .o_control_panel .breadcrumb {
            background-color: transparent !important;
        }

        .o_control_panel .breadcrumb-item::before {
            color: ${textMuted} !important;
        }

        .o_control_panel .breadcrumb-item > a {
            color: ${baseColor} !important;
            background-color: transparent !important;
        }

        .o_control_panel .breadcrumb-item > a:hover,
        .o_control_panel .breadcrumb-item > a:focus {
            color: ${textHover} !important;
            background-color: transparent !important;
        }

        .o_control_panel .o_last_breadcrumb_item,
        .o_control_panel .o_last_breadcrumb_item span,
        .o_control_panel .o_breadcrumb .text-truncate {
            color: ${textHeading} !important;
        }

        .o_control_panel .btn-light,
        .o_control_panel .btn-light:hover,
        .o_control_panel .btn-light:focus {
            background-color: ${isDark ? mixWithBlack(baseColor, 0.72) : mixWithWhite(baseColor, 0.94)} !important;
            color: ${textBody} !important;
            border-color: ${inputBorder} !important;
        }

        .o_control_panel .o_cp_pager .btn,
        .o_control_panel .o_cp_action_menus .btn {
            color: ${textBody} !important;
        }

        .o_control_panel .o_cp_pager .btn {
            background-color: ${statBtnBg} !important;
            border-color: ${statBtnBorder} !important;
        }

        /* ---- Form: tinted surround + sheet ---- */
        .o_form_view .o_form_sheet_bg {
            background: var(--company-theme-surround) !important;
            padding-top: 16px;
            padding-bottom: 16px;
        }

        .o_form_view .o_form_sheet {
            background: ${formSheet} !important;
            color: ${formSheetText} !important;
            border: 1px solid ${formSurround} !important;
            border-left: 4px solid ${baseColor} !important;
            border-radius: 6px !important;
            box-shadow: ${formShadow} !important;
            padding: 20px 28px !important;
        }

        @media (min-width: 992px) {
            .o_form_view .o_form_sheet {
                padding: 24px 32px !important;
            }
        }

        /* ---- Form stat buttons (Sales Order, Worksheet, etc.) ---- */
        .o_form_view .o-form-buttonbox .oe_stat_button {
            background-color: ${statBtnBg} !important;
            border: 1px solid ${statBtnBorder} !important;
        }

        .o_form_view .o-form-buttonbox .oe_stat_button:hover,
        .o_form_view .o-form-buttonbox .oe_stat_button:focus,
        .o_form_view .o-form-buttonbox .oe_stat_button:active {
            background-color: ${statBtnHover} !important;
            border-color: ${baseColor} !important;
        }

        /* ---- Form header & status bar (themed, no white gap) ---- */
        .o_form_view .o_form_statusbar {
            background: var(--company-theme-surround) !important;
            border-bottom: 1px solid ${darkenHex(baseColor, 0.75)} !important;
        }

        .o_form_view .o_statusbar_buttons {
            background: transparent !important;
        }

        .o_form_view .o_field_statusbar > .o_statusbar_status > .o_arrow_button {
            background-color: ${statusStepBg} !important;
            color: ${textBody} !important;
            border-color: ${darkenHex(baseColor, 0.82)} !important;
            font-weight: 600 !important;
        }

        .o_form_view .o_field_statusbar > .o_statusbar_status > .o_arrow_button:disabled:not(.o_arrow_button_current) {
            color: ${textSoft} !important;
            opacity: 1 !important;
        }

        .o_form_view .o_field_statusbar > .o_statusbar_status > .o_arrow_button.o_arrow_button_current:disabled,
        .o_form_view .o_field_statusbar > .o_statusbar_status > .o_arrow_button.o_arrow_button_current {
            background-color: ${baseColor} !important;
            color: ${navText} !important;
            border-color: ${borderColor} !important;
        }

        .o_form_view .o_field_statusbar > .o_statusbar_status > .o_arrow_button:not(.o_first):not(.o_last):before {
            border-left-color: var(--company-theme-surround) !important;
        }

        .o_form_view .o_field_statusbar > .o_statusbar_status > .o_arrow_button:not(.o_first):not(.o_last):after {
            border-left-color: ${statusStepBg} !important;
        }

        .o_form_view .o_field_statusbar > .o_statusbar_status > .o_arrow_button.o_arrow_button_current:disabled:after,
        .o_form_view .o_field_statusbar > .o_statusbar_status > .o_arrow_button.o_arrow_button_current:after {
            border-left-color: ${baseColor} !important;
        }

        .o_form_view .o_field_statusbar > .o_statusbar_status > .o_arrow_button.o_arrow_button_current:disabled + .btn:before,
        .o_form_view .o_field_statusbar > .o_statusbar_status > .o_arrow_button.o_arrow_button_current + .btn:before,
        .o_form_view .o_field_statusbar > .o_statusbar_status > .o_arrow_button.o_arrow_button_current:disabled:not(.o_first) + .o_arrow_button:before {
            border-left-color: ${borderColor} !important;
        }

        .o_form_view .o_field_statusbar > .o_statusbar_status > .o_arrow_button:hover:not(:disabled):not(.o_arrow_button_current) {
            background-color: ${statusStepHover} !important;
            color: ${textHover} !important;
        }

        .o_form_view .o_field_statusbar > .o_statusbar_status > .o_arrow_button:hover:not(:disabled):not(.o_arrow_button_current):after {
            border-left-color: ${statusStepHover} !important;
        }

        /* ---- Tabs: clean, brand accent on active only ---- */
        .o_form_view .nav-tabs {
            background: transparent !important;
            border-bottom: 2px solid ${formSurround} !important;
        }

        .o_form_view .nav-tabs .nav-link {
            color: ${textMuted} !important;
            background: transparent !important;
            border: none !important;
            border-bottom: 2px solid transparent !important;
            margin-bottom: -2px;
        }

        .o_form_view .nav-tabs .nav-link:hover {
            color: ${baseColor} !important;
            border-bottom-color: ${accentSoft} !important;
        }

        .o_form_view .nav-tabs .nav-link.active {
            color: ${baseColor} !important;
            background: transparent !important;
            border: none !important;
            border-bottom: 2px solid ${baseColor} !important;
            font-weight: 600;
        }

        /* ---- Inputs: white, readable ---- */
        .o_field_widget .o_input,
        .o_field_widget .o_input_dropdown,
        .o_field_widget textarea.o_input,
        .o_field_widget select.o_input,
        .o_field_widget .o_field_many2one_selection input {
            background-color: ${inputBg} !important;
            color: ${inputText} !important;
            border-color: ${inputBorder} !important;
        }

        .o_field_widget .o_input:focus,
        .o_field_widget .o_input_dropdown:focus-within,
        .o_field_widget textarea.o_input:focus {
            border-color: ${baseColor} !important;
            box-shadow: 0 0 0 2px ${accentSoft} !important;
        }

        .o_field_widget .o_input::placeholder,
        .o_field_widget textarea.o_input::placeholder {
            color: ${textMuted} !important;
            opacity: 1 !important;
        }

        /* ---- Buttons ---- */
        .btn-primary,
        .btn-outline-primary:focus,
        .btn-outline-primary:active,
        .text-bg-primary,
        .form-check-input:checked {
            background-color: ${baseColor} !important;
            border-color: ${borderColor} !important;
            color: ${navText} !important;
        }

        .form-check-input:focus {
            border-color: ${baseColor} !important;
            box-shadow: 0 0 0 0.25rem ${accentSoft} !important;
        }

        .form-switch .form-check-input:checked,
        .o_field_boolean_toggle .form-check-input:checked,
        .o_boolean_toggle .form-check-input:checked,
        .o_field_widget[name] .form-switch .form-check-input:checked {
            background-color: ${baseColor} !important;
            border-color: ${baseColor} !important;
            background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='-4 -4 8 8'%3e%3ccircle r='3' fill='%23fff'/%3e%3c/svg%3e") !important;
        }

        .o_list_view .o_list_record_selector .form-check-input:checked,
        .o_list_view .o_list_controller .form-check-input:checked {
            background-color: ${baseColor} !important;
            border-color: ${baseColor} !important;
        }

        .progress-bar,
        .progress-bar.bg-primary {
            background-color: ${baseColor} !important;
        }

        .badge.text-bg-primary,
        .o_tag.o_badge,
        .o_field_badge .badge.text-bg-primary {
            background-color: ${baseColor} !important;
            color: ${navText} !important;
        }

        a, .btn-link, .text-primary, .link-primary {
            color: ${baseColor};
        }

        .nav-link.active, .nav-pills .nav-link.active {
            background-color: ${baseColor} !important;
            color: ${navText} !important;
        }

        input[type="range"] {
            accent-color: ${baseColor};
        }

        .btn-primary:hover,
        .btn-primary:focus,
        .btn-primary:active {
            background-color: ${borderColor} !important;
            border-color: ${borderColor} !important;
            color: ${navText} !important;
        }

        .btn-outline-primary {
            color: ${baseColor} !important;
            border-color: ${baseColor} !important;
            background: ${btnOutlineBg} !important;
        }

        .btn-outline-primary:hover {
            background-color: ${baseColor} !important;
            color: ${navText} !important;
        }

        .o_form_view h1, .o_form_view h2 {
            color: ${textHeading} !important;
        }

        .o_form_label, .o_field_widget .o_form_label {
            color: ${textLabel} !important;
        }

        /* ---- Dropdowns: themed background ---- */
        .dropdown-menu,
        .o-dropdown--menu,
        .o-autocomplete--dropdown-menu,
        .ui-autocomplete.dropdown-menu {
            background-color: var(--company-theme-dropdown) !important;
            border-color: ${darkenHex(baseColor, 0.78)} !important;
            color: ${inputText} !important;
        }

        .dropdown-menu .dropdown-item,
        .o-dropdown--menu .dropdown-item,
        .o-autocomplete--dropdown-item .dropdown-item,
        .o-autocomplete--dropdown-item .ui-menu-item-wrapper,
        .ui-autocomplete .dropdown-item,
        .ui-autocomplete .ui-menu-item-wrapper {
            color: ${textBody} !important;
            background-color: transparent !important;
        }

        .dropdown-menu .dropdown-item:hover,
        .dropdown-menu .dropdown-item:focus,
        .dropdown-menu .dropdown-item.focus,
        .o-dropdown--menu .dropdown-item:hover,
        .o-dropdown--menu .dropdown-item.focus,
        .o-autocomplete--dropdown-item .dropdown-item:hover,
        .o-autocomplete--dropdown-item .ui-menu-item-wrapper:hover,
        .ui-autocomplete .dropdown-item:hover,
        .ui-autocomplete .ui-menu-item-wrapper:hover,
        .ui-autocomplete .ui-state-active {
            background-color: ${dropdownHover} !important;
            color: ${textHover} !important;
        }

        .dropdown-menu .dropdown-item.active,
        .dropdown-menu .dropdown-item:active,
        .o-dropdown--menu .dropdown-item.active,
        .o-autocomplete--dropdown-item .ui-state-active {
            background-color: ${baseColor} !important;
            color: ${navText} !important;
        }

        .dropdown-menu .dropdown-header,
        .o-dropdown--menu .dropdown-header {
            color: ${textMuted} !important;
            background-color: var(--company-theme-dropdown) !important;
        }

        .dropdown-divider {
            border-top-color: ${darkenHex(baseColor, 0.85)} !important;
        }

        /* Selection / many2one select menus */
        .o_select_menu .o_select_menu_toggler {
            background-color: var(--company-theme-dropdown) !important;
            color: ${inputText} !important;
            border-color: ${darkenHex(baseColor, 0.82)} !important;
        }

        .o_select_menu .o_select_menu_menu,
        .o_select_menu .o_select_menu_sticky,
        .o_select_menu .o_select_menu_group {
            background-color: var(--company-theme-dropdown) !important;
            color: ${textBody} !important;
        }

        .o_select_menu .o_select_menu_menu .dropdown-item:hover,
        .o_select_menu .o_select_menu_menu .dropdown-item.focus {
            background-color: ${dropdownHover} !important;
            color: ${textHover} !important;
        }

        /* Navbar & systray dropdowns */
        .o_main_navbar .dropdown-menu,
        .o_main_navbar .o-dropdown--menu,
        .o_control_panel .dropdown-menu,
        .o_control_panel .o-dropdown--menu {
            background-color: var(--company-theme-dropdown) !important;
            border-color: ${borderColor} !important;
        }

        .o_main_navbar .dropdown-menu .dropdown-item,
        .o_main_navbar .o-dropdown--menu .dropdown-item {
            color: ${textBody} !important;
        }

        .o_main_navbar .dropdown-menu .dropdown-item:hover,
        .o_main_navbar .dropdown-menu .dropdown-item.focus,
        .o_main_navbar .o-dropdown--menu .dropdown-item:hover,
        .o_main_navbar .o-dropdown--menu .dropdown-item.focus {
            background-color: ${dropdownHover} !important;
            color: ${textHover} !important;
        }

        /* ---- Waste manifest summary card ---- */
        .o_wmz_manifest_form .o_wmz_manifest_summary {
            background: ${wmzSummaryBg} !important;
            border-color: ${wmzSummaryBorder} !important;
        }

        .o_wmz_manifest_form .o_wmz_manifest_summary_label {
            color: ${textMuted} !important;
        }

        .o_wmz_manifest_form .o_wmz_manifest_summary_value {
            color: ${textBody} !important;
        }

        .o_wmz_manifest_form .o_wmz_manifest_subtitle {
            color: ${textSoft} !important;
        }

        /* ---- Waste manifest status alerts ---- */
        .o_wmz_manifest_alert.alert-success {
            background-color: ${isDark ? rgbaFromHex("#22c55e", 0.16) : "#d1fae5"} !important;
            background-image: none !important;
            border-color: ${isDark ? rgbaFromHex("#22c55e", 0.42) : "#a7f3d0"} !important;
            color: ${isDark ? "#bbf7d0" : "#065f46"} !important;
        }

        .o_wmz_manifest_alert.alert-danger {
            background-color: ${isDark ? rgbaFromHex("#ef4444", 0.16) : "#fee2e2"} !important;
            background-image: none !important;
            border-color: ${isDark ? rgbaFromHex("#ef4444", 0.42) : "#fecaca"} !important;
            color: ${isDark ? "#fecaca" : "#991b1b"} !important;
        }

        .o_wmz_manifest_alert.alert-info {
            background-color: ${isDark ? rgbaFromHex("#3b82f6", 0.16) : "#dbeafe"} !important;
            background-image: none !important;
            border-color: ${isDark ? rgbaFromHex("#3b82f6", 0.42) : "#bfdbfe"} !important;
            color: ${isDark ? "#bfdbfe" : "#1e40af"} !important;
        }

        .o_wmz_manifest_alert .fa,
        .o_wmz_manifest_alert strong,
        .o_wmz_manifest_alert .o_field_widget,
        .o_wmz_manifest_alert .o_field_widget span {
            color: inherit !important;
        }

        .o_wmz_manifest_form .ribbon span.text-bg-success {
            background-color: ${isDark ? "#15803d" : "#198754"} !important;
            color: #ffffff !important;
        }

        .o_wmz_manifest_form .ribbon span.text-bg-danger {
            background-color: ${isDark ? "#b91c1c" : "#dc3545"} !important;
            color: #ffffff !important;
        }

        /* ---- Chatter / mail thread ---- */
        .o-mail-Form-chatter,
        .o-mail-ChatterContainer,
        .o-mail-Chatter {
            background-color: ${chatterBg} !important;
        }

        .o-mail-Chatter-top,
        .o-mail-Chatter-topbar {
            background-color: ${chatterTopbar} !important;
            background-image: none !important;
        }

        .o-mail-Chatter .o-mail-Chatter-logNote.btn-secondary,
        .o-mail-Chatter .o-mail-Chatter-activity.btn-secondary,
        .o-mail-Chatter .btn-secondary {
            background-color: ${isDark ? mixWithBlack(baseColor, 0.74) : "#f8f9fa"} !important;
            border-color: ${inputBorder} !important;
            color: ${textBody} !important;
        }

        .o-mail-Chatter .o-mail-Chatter-sendMessage.btn-primary,
        .o-mail-Chatter .o-mail-Chatter-sendMessage.btn-primary.active {
            color: ${navText} !important;
        }

        .o-mail-Chatter .btn-link.text-action,
        .o-mail-Chatter .o-mail-Followers-button,
        .o-mail-Chatter .o-mail-Chatter-attachFiles {
            color: ${textMuted} !important;
        }

        .o-mail-NotificationMessage {
            color: ${textMuted} !important;
        }

        .o-mail-NotificationMessage a,
        .o-mail-NotificationMessage .o_mail_redirect {
            color: ${isDark ? mixWithWhite(baseColor, 0.55) : baseColor} !important;
        }

        .o-mail-Message-author strong,
        .o-mail-Message-body,
        .o-mail-Message-body p,
        .o-mail-Message-body span {
            color: ${textBody} !important;
        }

        .o-mail-Message-body em,
        .o-mail-Message-date.text-muted,
        .o-mail-Message .text-muted,
        .o-mail-Message .text-500,
        .o-mail-Message .text-600 {
            color: ${textMuted} !important;
        }

        .o-mail-Message .o-mail-Message-bubble.bg-info-light,
        .o-mail-Message .o-mail-Message-bubble.bg-success-light,
        .o-mail-Message .o-mail-Message-bubble.bg-warning-light {
            background-color: ${chatterBubbleIn} !important;
            background-image: none !important;
            border-color: ${chatterBubbleInBorder} !important;
            opacity: 1 !important;
        }

        .o-mail-Message.o-selfAuthored .o-mail-Message-bubble.bg-success-light {
            background-color: ${chatterBubbleOut} !important;
            border-color: ${chatterBubbleOutBorder} !important;
        }

        .o-mail-Composer-input,
        .o-mail-Composer .o-mail-Composer-input {
            background-color: ${inputBg} !important;
            color: ${inputText} !important;
            border-color: ${inputBorder} !important;
        }

        .o-mail-Message-actions .bg-view {
            background-color: ${isDark ? mixWithBlack(baseColor, 0.74) : "#ffffff"} !important;
        }

        .o-mail-Thread hr,
        .o-mail-ActivityList hr,
        .o-mail-AttachmentBox hr {
            border-color: ${chatterBorder} !important;
            opacity: 1 !important;
        }

        ${isDark ? `
        .o-mail-Message-body div,
        .o-mail-Message-body table,
        .o-mail-Message-body td,
        .o-mail-Message-body th,
        .o-mail-Message-body p {
            background-color: transparent !important;
            color: inherit !important;
        }

        .o-mail-Message-body a {
            color: ${mixWithWhite(baseColor, 0.55)} !important;
        }
        ` : ""}
    `;
}

function applyTheme(baseColor) {
    const dark = isDarkMode();
    document.documentElement.dataset.companyColorScheme = dark ? "dark" : "light";

    let style = document.getElementById(STYLE_ID);
    if (!style) {
        style = document.createElement("style");
        style.id = STYLE_ID;
        style.type = "text/css";
        document.head.appendChild(style);
    }
    style.textContent = buildThemeCss(baseColor, isDarkMode());
}

const companySmartThemeService = {
    dependencies: ["orm"],
    start(_env, { orm }) {
        let lastCompanyId = null;
        let lastThemeColor = null;
        let lastDarkMode = null;
        let timer = null;

        const refresh = async () => {
            try {
                const result = await orm.call("res.company", "get_company_theme", [], {});
                if (!result) {
                    return;
                }
                const companyId = result.company_id;
                const themeColor = result.theme_color || DEFAULT_COLOR;
                const dark = isDarkMode();
                if (
                    companyId !== lastCompanyId ||
                    themeColor !== lastThemeColor ||
                    dark !== lastDarkMode
                ) {
                    lastCompanyId = companyId;
                    lastThemeColor = themeColor;
                    lastDarkMode = dark;
                    applyTheme(themeColor);
                }
            } catch (err) {
                console.error("company_smart_theme.refresh error:", err);
            }
        };

        const boot = () => {
            refresh();
            timer = setInterval(refresh, POLL_MS);
        };

        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", boot, { once: true });
        } else {
            boot();
        }

        return {
            applyColor(color) {
                const themeColor = color || DEFAULT_COLOR;
                lastThemeColor = themeColor;
                applyTheme(themeColor);
            },
            destroy() {
                if (timer) {
                    clearInterval(timer);
                }
            },
        };
    },
};

document.documentElement.dataset.companyColorScheme = isDarkMode() ? "dark" : "light";

registry.category("services").add("company_smart_theme", companySmartThemeService);
