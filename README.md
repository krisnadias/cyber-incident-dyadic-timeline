# Dyadic Cyber Incident Timeline

Interactive timeline of cyber incidents and the legal and political responses
between any two countries, built on the
[European Repository of Cyber Incidents (EuRepoC)](https://eurepoc.eu/) database.

**Interactive Graph Available at: https://krisnadias.github.io/cyber-incident-dyadic-timeline/**

Pick two countries from the menu and the chart renders:

- **Above the axis** — cyber incidents as lollipops (height = EuRepoC weighted
  cyber intensity; orange = country A initiated, violet = country B initiated;
  a dark red outline marks a state or state-affiliated initiator).
- **Below the axis** — legal responses (diamonds, one lane per EuRepoC codebook
  section 52 type) and political responses (triangles, one lane per section 25
  actor × kind), on the side of the responding country.
- **Right axis** — the HIIK offline conflict level (0–5) as a dark red step line.

Click any marker to reveal the incident's full description, its legal and
political responses, and the source URLs below the graph; the incident and all
of its responses are highlighted together on the chart. The **Print graph**
button prints the current chart plus the open details panel.

## Files

| File | Purpose |
|---|---|
| `index.html` | The page. Fully self-contained with the two files below — works from `file://`, any static host, or GitHub Pages. |
| `data.js` | Pre-processed incident data (generated, do not edit by hand). |
| `plotly.min.js` | Vendored Plotly.js, so no CDN is needed. |
| `build_data.py` | Regenerates `data.js` from a EuRepoC Excel export. |

## Data citation

European Repository of Cyber Incidents (accessed 16 July 2026) https://eurepoc.eu/table-view/

the European Repository of Cyber Incidents (EuRepoC) and is licensed under 
Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).

