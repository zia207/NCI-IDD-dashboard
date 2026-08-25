"""
build_geo.py
============
Builds a compact GeoJSON of the 10 NYS regions used in the dashboard by mapping
each of New York's 62 counties to its region (official REDC groupings) and
dissolving county polygons into region polygons. Output: nys_regions.geojson
(properties.region = region name), simplified to keep the dashboard file small.
"""
import json
import geopandas as gpd

# County (by name) -> region. Official NYS Regional Economic Development groupings.
COUNTY_REGION = {
    # Western New York
    "Allegany": "Western New York", "Cattaraugus": "Western New York",
    "Chautauqua": "Western New York", "Erie": "Western New York",
    "Niagara": "Western New York",
    # Finger Lakes
    "Genesee": "Finger Lakes", "Livingston": "Finger Lakes", "Monroe": "Finger Lakes",
    "Ontario": "Finger Lakes", "Orleans": "Finger Lakes", "Seneca": "Finger Lakes",
    "Wayne": "Finger Lakes", "Wyoming": "Finger Lakes", "Yates": "Finger Lakes",
    # Southern Tier
    "Broome": "Southern Tier", "Chemung": "Southern Tier", "Chenango": "Southern Tier",
    "Delaware": "Southern Tier", "Schuyler": "Southern Tier", "Steuben": "Southern Tier",
    "Tioga": "Southern Tier", "Tompkins": "Southern Tier",
    # Central New York
    "Cayuga": "Central New York", "Cortland": "Central New York",
    "Madison": "Central New York", "Onondaga": "Central New York",
    "Oswego": "Central New York",
    # Mohawk Valley
    "Fulton": "Mohawk Valley", "Herkimer": "Mohawk Valley", "Montgomery": "Mohawk Valley",
    "Oneida": "Mohawk Valley", "Otsego": "Mohawk Valley", "Schoharie": "Mohawk Valley",
    # North Country
    "Clinton": "North Country", "Essex": "North Country", "Franklin": "North Country",
    "Hamilton": "North Country", "Jefferson": "North Country", "Lewis": "North Country",
    "St. Lawrence": "North Country",
    # Capital Region
    "Albany": "Capital Region", "Columbia": "Capital Region", "Greene": "Capital Region",
    "Rensselaer": "Capital Region", "Saratoga": "Capital Region",
    "Schenectady": "Capital Region", "Warren": "Capital Region",
    "Washington": "Capital Region",
    # Hudson Valley (Mid-Hudson)
    "Dutchess": "Hudson Valley", "Orange": "Hudson Valley", "Putnam": "Hudson Valley",
    "Rockland": "Hudson Valley", "Sullivan": "Hudson Valley", "Ulster": "Hudson Valley",
    "Westchester": "Hudson Valley",
    # New York City
    "Bronx": "New York City", "Kings": "New York City", "New York": "New York City",
    "Queens": "New York City", "Richmond": "New York City",
    # Long Island
    "Nassau": "Long Island", "Suffolk": "Long Island",
}

g = json.load(open("us_counties.json"))
ny = [f for f in g["features"] if str(f.get("id", "")).startswith("36")]
for f in ny:
    f["properties"]["region"] = COUNTY_REGION.get(f["properties"]["NAME"])

missing = [f["properties"]["NAME"] for f in ny if not f["properties"]["region"]]
assert not missing, f"Unmapped counties: {missing}"

gdf = gpd.GeoDataFrame.from_features(ny, crs="EPSG:4326")
regions = gdf.dissolve(by="region", as_index=False)[["region", "geometry"]]
# Simplify to shrink embedded size (tolerance in degrees ~ a few hundred meters)
regions["geometry"] = regions["geometry"].simplify(0.005, preserve_topology=True)

regions.to_file("nys_regions.geojson", driver="GeoJSON")
out = json.load(open("nys_regions.geojson"))
print(f"Regions: {len(out['features'])}")
print("Names:", sorted(f["properties"]["region"] for f in out["features"]))
import os
print(f"GeoJSON size: {os.path.getsize('nys_regions.geojson')/1024:.0f} KB")
