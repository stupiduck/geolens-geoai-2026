// ArcGIS client keys are public browser credentials. Use a basemap-only key
// restricted to the application's origins, never an account/admin secret.
const env = (import.meta as ImportMeta & {env: Record<string,string|undefined>}).env;
const key = env.VITE_ARCGIS_API_KEY?.trim();
export const imagery = key ? {
  label: 'Satellite · Esri',
  tiles: [`https://ibasemaps-api.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}?token=${encodeURIComponent(key)}`],
  maxzoom: 19,
  attribution: '<a href="https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9">Esri World Imagery</a> · Esri, Vantor, Earthstar Geographics, and the GIS User Community',
} : {
  label: 'Satellite · 2024',
  tiles: ['https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2024_3857/default/g/{z}/{y}/{x}.jpg'],
  maxzoom: 14,
  attribution: '<a href="https://maps.eox.at/">EOX::Maps</a> · Contains modified Copernicus Sentinel data 2024 · <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/">CC BY-NC-SA 4.0</a>',
};
