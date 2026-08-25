/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

function normalizeHex(color) {
    const value = (color || "").trim().toLowerCase();
    if (!value) {
        return "";
    }
    if (value.startsWith("#")) {
        return value.length === 4
            ? `#${value[1]}${value[1]}${value[2]}${value[2]}${value[3]}${value[3]}`
            : value;
    }
    return `#${value}`;
}

export class ThemePalettePickerField extends Component {
    static template = "company_smart_theme.ThemePalettePickerField";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.companySmartTheme = useService("company_smart_theme");
    }

    get paletteColors() {
        const raw = this.props.record.data.theme_palette || "";
        const colors = raw
            .split(",")
            .map((color) => normalizeHex(color))
            .filter(Boolean);
        const current = normalizeHex(this.props.record.data.theme_color);
        if (current && !colors.some((color) => color === current)) {
            colors.unshift(current);
        }
        return colors.length ? colors : [current || "#4caf50"];
    }

    get selectedColor() {
        return normalizeHex(this.props.record.data.theme_color);
    }

    isSelected(color) {
        return normalizeHex(color) === this.selectedColor;
    }

    async onSelectColor(color) {
        if (this.props.readonly) {
            return;
        }
        const normalized = normalizeHex(color);
        if (!normalized) {
            return;
        }

        await this.props.record.update({
            [this.props.name]: normalized,
            auto_theme_from_logo: false,
        });

        this.companySmartTheme.applyColor(normalized);

        const resId = this.props.record.resId;
        if (!resId) {
            return;
        }

        try {
            await this.orm.write(this.props.record.resModel, [resId], {
                theme_color: normalized,
                auto_theme_from_logo: false,
            });
        } catch (err) {
            console.error("company_smart_theme: failed to save theme color", err);
        }
    }
}

export const themePalettePickerField = {
    component: ThemePalettePickerField,
    supportedTypes: ["char"],
    fieldDependencies: [
        { name: "theme_palette", type: "text" },
        { name: "auto_theme_from_logo", type: "boolean" },
    ],
};

registry.category("fields").add("theme_palette_picker", themePalettePickerField);
