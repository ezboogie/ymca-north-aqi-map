# YMCA of the North AQI Map

An interactive Leaflet map showing YMCA of the North branches, overnight camps, and day camps across Minnesota and western Wisconsin.

## Live site

The production site is deployed automatically to GitHub Pages from the `main` branch.

## Data and services

- OpenStreetMap supplies the base map.
- PurpleAir supplies current outdoor PM2.5 readings through its authenticated API.
- `scripts/fetch_aqi.py` applies the EPA PurpleAir correction, converts corrected PM2.5 to the current US EPA AQI scale, and matches every YMCA to the nearest recent sensor within 80 km.
- YMCA coordinates are maintained in `locations.json`.

## Configure PurpleAir

Add a GitHub Actions repository secret named `PURPLEAIR_API_KEY`. The key remains server-side and is never exposed to the public website. After adding the secret, manually run the **Deploy to GitHub Pages** workflow once; scheduled refreshes run hourly at 17 minutes past the hour.

PurpleAir uses a points-based API access model. The workflow makes one regional sensor request per run.

## Deployment

Pushes to `main`, manual runs, and the hourly schedule execute `.github/workflows/deploy-pages.yml`. If the secret is missing, the site still deploys its YMCA markers and displays a configuration warning instead of exposing or fabricating AQI values.
