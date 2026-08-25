/** @odoo-module **/

(function loadCompanyThemeCss() {
    const id = "company-smart-theme-frontend";
    if (document.getElementById(id)) {
        return;
    }
    const link = document.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.type = "text/css";
    link.href = "/company_smart_theme/frontend.css?t=" + Date.now();
    document.head.appendChild(link);
})();
