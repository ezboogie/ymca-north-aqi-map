# YMCA of the North AQI Map

An interactive Leaflet map showing YMCA of the North branches, overnight camps, and day camps across Minnesota and western Wisconsin.

## Live site

The production site is deployed automatically to GitHub Pages from the `main` branch.

## Data and services

- OpenStreetMap supplies the base map.
- PurpleAir is referenced as the intended live AQI overlay.
- YMCA coordinates are maintained directly in `index.html`.

## Important AQI note

PurpleAir's supported data API requires an API key and uses a points-based access model. The current prototype retains the supplied tile-layer URL, but that URL is not documented as a supported public PurpleAir tile endpoint. The YMCA markers and OpenStreetMap layer work independently; the AQI overlay should be replaced with a supported, authenticated integration before it is relied on operationally.

## Deployment

Pushes to `main` run the GitHub Pages workflow in `.github/workflows/deploy-pages.yml`.
