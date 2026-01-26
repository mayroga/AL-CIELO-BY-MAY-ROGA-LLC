# Descarga de datos geográficos de Cuba (OpenStreetMap Vector Tiles)
wget https://download.geofabrik.de/central-america/cuba-latest.osm.pbf
# Conversión a formato offline para la App AL CIELO
osmtogo cuba-latest.osm.pbf --output=static/maps/cuba_full.mbtiles
echo "Mapa de Cuba (Pinar a Oriente + Isla de la Juventud) listo para AL CIELO."
