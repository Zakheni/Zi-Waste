"""Geocoding and distance helpers using free OpenStreetMap Nominatim."""
import hashlib
import json
import logging
import math
import re
import time
import urllib.parse
import urllib.request

from odoo import api, models

try:
    import requests
except ImportError:  # pragma: no cover - requests is bundled with Odoo
    requests = None

_logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = (
    "WasteManagementZakheni/1.0 (Waste Management; mailto:admin@ziwaste.co.za)"
)
NOMINATIM_HEADERS = {
    "User-Agent": NOMINATIM_USER_AGENT,
    "Accept": "application/json",
    "Accept-Language": "en",
}
_LAST_NOMINATIM_CALL = 0.0
_MIN_INTERVAL_SEC = 1.05
_MAX_FALLBACK_ATTEMPTS = 12

SA_PROVINCE_NAME_TO_CODE = {
    "eastern cape": "EC",
    "free state": "FS",
    "gauteng": "GP",
    "kwazulu-natal": "KZN",
    "kwa zulu natal": "KZN",
    "limpopo": "LP",
    "mpumalanga": "MP",
    "northern cape": "NC",
    "north west": "NW",
    "western cape": "WC",
}


class WmzGeoMixin(models.AbstractModel):
    _name = "wmz.geo.mixin"
    _description = "WMZ Geocoding and Distance Utilities"

    @api.model
    def haversine_km(self, lat1, lon1, lat2, lon2):
        """Return great-circle distance in kilometres between two points."""
        if not all(v is not None for v in (lat1, lon1, lat2, lon2)):
            return False
        r = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @api.model
    def _geocode_cache_key(self, parts):
        if isinstance(parts, str):
            raw = parts.strip().lower()
        else:
            raw = "|".join((p or "").strip().lower() for p in parts)
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    @api.model
    def _geocode_from_cache(self, cache_key):
        param = self.env["ir.config_parameter"].sudo()
        raw = param.get_param(f"wmz.geocode.{cache_key}")
        if not raw:
            return None
        try:
            data = json.loads(raw)
            if data.get("lat") is not None and data.get("lon") is not None:
                return {
                    "lat": float(data["lat"]),
                    "lon": float(data["lon"]),
                    "components": data.get("components") or {},
                    "display_name": data.get("display_name") or "",
                }
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return None

    @api.model
    def _geocode_to_cache(self, cache_key, lat, lon, components=None, display_name=None):
        param = self.env["ir.config_parameter"].sudo()
        param.set_param(
            f"wmz.geocode.{cache_key}",
            json.dumps({
                "lat": lat,
                "lon": lon,
                "components": components or {},
                "display_name": display_name or "",
            }),
        )

    @api.model
    def _throttle_nominatim(self):
        global _LAST_NOMINATIM_CALL
        elapsed = time.time() - _LAST_NOMINATIM_CALL
        if elapsed < _MIN_INTERVAL_SEC:
            time.sleep(_MIN_INTERVAL_SEC - elapsed)
        _LAST_NOMINATIM_CALL = time.time()

    @api.model
    def _clean_address_part(self, value):
        if not value:
            return ""
        return re.sub(r"\s+", " ", str(value).strip().rstrip(","))

    @api.model
    def format_partner_address(self, partner):
        """Build a single-line address from a res.partner."""
        if not partner:
            return ""
        parts = []
        for value in (
            partner.street,
            partner.street2,
            partner.city,
            partner.zip,
            partner.state_id.name if partner.state_id else None,
            partner.country_id.name if partner.country_id else "South Africa",
        ):
            cleaned = self._clean_address_part(value)
            if cleaned and (not parts or cleaned.lower() != parts[-1].lower()):
                parts.append(cleaned)
        return ", ".join(parts)

    @api.model
    def _extract_components(self, address_block):
        """Parse Nominatim address details into street, suburb, city, province code."""
        if not address_block:
            return {}
        suburb = (
            address_block.get("suburb")
            or address_block.get("neighbourhood")
            or address_block.get("township")
            or address_block.get("quarter")
            or ""
        )
        city = (
            address_block.get("city")
            or address_block.get("town")
            or address_block.get("municipality")
            or address_block.get("village")
            or address_block.get("county")
            or ""
        )
        street = address_block.get("road") or address_block.get("pedestrian") or ""
        house_number = address_block.get("house_number") or ""
        if house_number and street:
            street = f"{house_number} {street}".strip()

        state_name = (address_block.get("state") or "").strip().lower()
        province_code = SA_PROVINCE_NAME_TO_CODE.get(state_name, False)
        return {
            "street": street,
            "suburb": suburb,
            "city": city,
            "province": province_code,
        }

    @api.model
    def _expand_street_abbreviations(self, query):
        """Expand common SA street suffixes to improve Nominatim matches."""
        replacements = (
            (r"\bRd\b", "Road"),
            (r"\bSt\b", "Street"),
            (r"\bAv\b", "Avenue"),
            (r"\bAve\b", "Avenue"),
            (r"\bDr\b", "Drive"),
            (r"\bLn\b", "Lane"),
            (r"\bCrt\b", "Court"),
            (r"\bCt\b", "Court"),
            (r"\bPl\b", "Place"),
            (r"\bCres\b", "Crescent"),
        )
        result = query
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result

    @api.model
    def _split_address_query(self, query):
        return [self._clean_address_part(part) for part in query.split(",") if self._clean_address_part(part)]

    @api.model
    def _normalize_geocode_phrase(self, value):
        """Strip descriptive noise common in SA farm and site addresses."""
        cleaned = self._clean_address_part(value)
        if not cleaned:
            return ""
        cleaned = re.sub(
            r"\b(accessible\s+from|near|off|via|adjacent\s+to|located\s+(?:at|on|near))\s+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"^\b(?:portion|erf|farm|plot)\s+\d+\s*,?\s*", "", cleaned, flags=re.IGNORECASE)
        return self._clean_address_part(cleaned)

    @api.model
    def _extract_road_segment(self, text):
        """Return a road-like substring when present."""
        if not text:
            return ""
        match = re.search(
            r"([\w\s\-']+(?:Road|Street|St|Rd|Drive|Dr|Avenue|Ave|Highway|Way|Lane|Boulevard|Blvd))",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            return self._expand_street_abbreviations(self._clean_address_part(match.group(1)))
        return ""

    @api.model
    def _fallback_geocode_queries(self, query):
        """Build progressively broader queries when the exact address is unknown to OSM."""
        queries = []
        seen = set()

        def add(value):
            cleaned = self._clean_address_part(value)
            key = cleaned.lower()
            if cleaned and key not in seen:
                seen.add(key)
                queries.append(cleaned)

        normalized_query = self._normalize_geocode_phrase(query)
        add(query)
        add(normalized_query)
        add(self._expand_street_abbreviations(query))
        add(self._expand_street_abbreviations(normalized_query))

        parts = self._split_address_query(query)
        normalized_parts = [
            self._normalize_geocode_phrase(part) for part in parts if self._normalize_geocode_phrase(part)
        ]
        country = "South Africa"
        if parts and "south africa" in parts[-1].lower():
            country = parts[-1]
            body_parts = parts[:-1]
            normalized_body = normalized_parts[:-1]
        else:
            body_parts = parts
            normalized_body = normalized_parts
            add(f"{query}, {country}")
            add(f"{normalized_query}, {country}")

        if len(body_parts) >= 2:
            add(", ".join(body_parts[1:]))
            add(", ".join(normalized_body[1:] if len(normalized_body) >= 2 else body_parts[1:]))
            add(self._expand_street_abbreviations(", ".join(body_parts[1:])))

        postcode = next((part for part in body_parts if re.fullmatch(r"\d{4}", part)), None)
        city = body_parts[-1] if body_parts else ""
        normalized_city = self._normalize_geocode_phrase(city)

        if postcode:
            idx = body_parts.index(postcode)
            before = body_parts[:idx]
            if before:
                city = before[-1]
                normalized_city = self._normalize_geocode_phrase(city)
                suburb = before[-2] if len(before) >= 2 else None
                add(f"{postcode}, {city}, {country}")
                if suburb:
                    add(f"{suburb}, {city}, {postcode}, {country}")
                    add(f"{suburb}, {city}, {country}")
                add(f"{city}, {country}")

        if normalized_city:
            add(f"{normalized_city}, {country}")

        for part in normalized_body:
            road = self._extract_road_segment(part)
            if road and normalized_city:
                add(f"{road}, {normalized_city}, {country}")
                add(self._expand_street_abbreviations(f"{road}, {normalized_city}, {country}"))

        if len(body_parts) >= 2:
            add(", ".join(body_parts[-2:] + [country]))
            add(", ".join(normalized_body[-2:] + [country] if len(normalized_body) >= 2 else body_parts[-2:] + [country]))
        if len(body_parts) >= 3:
            add(", ".join(body_parts[-3:] + [country]))
            add(", ".join(normalized_body[-3:] + [country] if len(normalized_body) >= 3 else body_parts[-3:] + [country]))

        return queries

    @api.model
    def _nominatim_search(self, query, countrycodes="za"):
        params = {
            "q": query,
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
        }
        if countrycodes:
            params["countrycodes"] = countrycodes
        self._throttle_nominatim()
        try:
            if requests is not None:
                response = requests.get(
                    NOMINATIM_URL,
                    params=params,
                    headers=NOMINATIM_HEADERS,
                    timeout=15,
                )
                response.raise_for_status()
                return response.json()

            url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
            request = urllib.request.Request(url, headers=NOMINATIM_HEADERS)
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            _logger.warning("Nominatim lookup failed for %r: %s", query, exc)
            raise

    @api.model
    def _parse_nominatim_item(self, item, fallback_query):
        lat = float(item["lat"])
        lon = float(item["lon"])
        components = self._extract_components(item.get("address") or {})
        display_name = item.get("display_name") or fallback_query
        return lat, lon, components, display_name

    @api.model
    def _is_south_african_result(self, item):
        address = item.get("address") or {}
        country_code = (address.get("country_code") or "").lower()
        return not country_code or country_code == "za"

    @api.model
    def _search_nominatim_result(self, query):
        for countrycodes in ("za", None):
            try:
                payload = self._nominatim_search(query, countrycodes=countrycodes)
            except Exception:
                continue
            if not payload:
                continue
            item = payload[0]
            if countrycodes is None and not self._is_south_african_result(item):
                continue
            return self._parse_nominatim_item(item, query)
        return None

    @api.model
    def geocode_query(self, query):
        """Geocode a single free-text address. Returns dict with lat, lon, components."""
        query = self._clean_address_part(query)
        if not query:
            return {
                "lat": False,
                "lon": False,
                "components": {},
                "display_name": "",
                "approximate": False,
            }

        original_key = query.lower()
        for attempt_query in self._fallback_geocode_queries(query)[:_MAX_FALLBACK_ATTEMPTS]:
            cache_key = self._geocode_cache_key(attempt_query)
            cached = self._geocode_from_cache(cache_key)
            if cached:
                return {
                    "lat": cached["lat"],
                    "lon": cached["lon"],
                    "components": cached.get("components") or {},
                    "display_name": cached.get("display_name") or attempt_query,
                    "approximate": attempt_query.lower() != original_key,
                }

            parsed = self._search_nominatim_result(attempt_query)
            if not parsed:
                continue

            lat, lon, components, display_name = parsed
            self._geocode_to_cache(
                cache_key,
                lat,
                lon,
                components,
                display_name=display_name,
            )
            return {
                "lat": lat,
                "lon": lon,
                "components": components,
                "display_name": display_name,
                "approximate": attempt_query.lower() != original_key,
            }

        return {
            "lat": False,
            "lon": False,
            "components": {},
            "display_name": query,
            "approximate": False,
        }

    @api.model
    def geocode_address(self, street=None, city=None, state=None, suburb=None, country="South Africa"):
        """Geocode structured address parts (legacy). Returns (lat, lon) or (False, False)."""
        if street and "," in street and not any((suburb, city, state)):
            result = self.geocode_query(street)
            return result["lat"], result["lon"]

        parts = [p for p in (street, suburb, city, state, country) if p]
        if not parts:
            return False, False

        query = ", ".join(self._clean_address_part(p) for p in parts if p)
        result = self.geocode_query(query)
        return result["lat"], result["lon"]

    @api.model
    def geocode_partner(self, partner):
        """Geocode a res.partner record."""
        if not partner:
            return False, False
        query = self.format_partner_address(partner)
        if not query:
            return False, False
        result = self.geocode_query(query)
        return result["lat"], result["lon"]
