/** @odoo-module **/

import { Component, onMounted, onWillUnmount, onPatched, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { loadJS, loadCSS } from "@web/core/assets";

const LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
const LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";

export class ProviderMapField extends Component {
    static template = "waste_management_zakheni.ProviderMapField";
    static props = { ...standardFieldProps };

    setup() {
        this.mapRef = useRef("mapContainer");
        this.map = null;
        this.markers = [];

        onMounted(() => this._renderMap());
        onPatched(() => this._renderMap());
        onWillUnmount(() => this._destroyMap());
    }

    get mapData() {
        const raw = this.props.record.data[this.props.name];
        if (!raw) {
            return { job: {}, providers: [] };
        }
        try {
            return JSON.parse(raw);
        } catch {
            return { job: {}, providers: [] };
        }
    }

    get hasMapData() {
        const data = this.mapData;
        return !!(data.job && data.job.lat) || (data.providers || []).some((p) => p.lat && p.lon);
    }

    async _ensureLeaflet() {
        if (window.L) {
            return window.L;
        }
        await loadCSS(LEAFLET_CSS);
        await loadJS(LEAFLET_JS);
        return window.L;
    }

    _destroyMap() {
        if (this.map) {
            this.map.remove();
            this.map = null;
        }
        this.markers = [];
    }

    _rankIcon(L, rank, isPickup = false) {
        const classes = ["o_wmz_map_marker"];
        if (isPickup) {
            classes.push("o_wmz_map_marker_pickup");
        } else if (rank === 1) {
            classes.push("o_wmz_map_marker_top");
        }
        const label = isPickup ? "P" : String(rank || "");
        return L.divIcon({
            className: "",
            html: `<div class="${classes.join(" ")}">${label}</div>`,
            iconSize: [32, 32],
            iconAnchor: [16, 16],
        });
    }

    async _renderMap() {
        const el = this.mapRef.el;
        if (!el || !this.hasMapData) {
            this._destroyMap();
            return;
        }
        this._destroyMap();
        const data = this.mapData;
        const L = await this._ensureLeaflet();
        if (!L || !this.mapRef.el) {
            return;
        }

        const job = data.job || {};
        const providers = data.providers || [];
        const hasJob = job.lat && job.lon;
        const defaultLat = hasJob ? job.lat : -28.4793;
        const defaultLon = hasJob ? job.lon : 24.6727;

        this.map = L.map(el, { scrollWheelZoom: true }).setView([defaultLat, defaultLon], hasJob ? 10 : 6);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution: "&copy; OpenStreetMap contributors",
        }).addTo(this.map);

        const bounds = [];
        if (hasJob) {
            const jobMarker = L.marker([job.lat, job.lon], {
                icon: this._rankIcon(L, 0, true),
            }).addTo(this.map);
            jobMarker.bindPopup(`<strong>Pickup</strong><br/>${job.label || ""}`);
            this.markers.push(jobMarker);
            bounds.push([job.lat, job.lon]);
        }

        providers.forEach((p) => {
            if (!p.lat || !p.lon) {
                return;
            }
            const marker = L.marker([p.lat, p.lon], {
                icon: this._rankIcon(L, p.rank),
            }).addTo(this.map);
            marker.bindPopup(
                `<strong>#${p.rank} ${p.name}</strong><br/>${p.address || p.city || ""}<br/><strong>${p.distance_km} km</strong>`
            );
            this.markers.push(marker);
            bounds.push([p.lat, p.lon]);
        });

        if (bounds.length > 1) {
            this.map.fitBounds(bounds, { padding: [40, 40] });
        }
        setTimeout(() => this.map && this.map.invalidateSize(), 250);
    }
}

export const providerMapField = {
    component: ProviderMapField,
    supportedTypes: ["text", "char"],
};

registry.category("fields").add("provider_map", providerMapField);
