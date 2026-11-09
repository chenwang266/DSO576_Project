"""Run the published visual dashboard inside Streamlit, with bundled local data.

Launch from any directory: streamlit run /path/to/streamlit_visual.py
The frontend remains the source of truth for layout and calculations.
"""
import base64
import gzip
import json
from pathlib import Path
import re

SITE = Path(__file__).resolve().parent / "site" / "dist"


def script(source):
    """Keep JavaScript strings containing HTML from closing the script tag."""
    return "<script>" + re.sub(r"</script", r"<\\/script", source, flags=re.I) + "</script>"


def build_dashboard(directory=SITE):
    """Package the exact Site frontend without external hosting or an HTTP server."""
    directory = Path(directory)
    catalog = json.loads((directory / "assets/catalog.json").read_text())
    names = ["catalog.json", *dict.fromkeys(catalog["bundles"].values())]
    payloads = {}
    for name in names:
        path = (directory / "assets" / name).resolve()
        if not path.is_relative_to((directory / "assets").resolve()):
            raise ValueError(f"Invalid asset path: {name}")
        payloads["assets/" + name] = base64.b64encode(
            gzip.compress(path.read_bytes(), mtime=0)
        ).decode("ascii")

    # srcdoc iframes cannot fetch repository-relative files. Decode local,
    # compressed assets lazily instead; no remote Site or CDN is required.
    loader = "const bundledAssets = " + json.dumps(payloads) + ";\n" + """
async function fetchAsset(path) {
  if (!(path in bundledAssets)) throw Error('Missing bundled evidence: ' + path);
  const bytes = Uint8Array.from(atob(bundledAssets[path]), c => c.charCodeAt(0));
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
  const value = await new Response(stream).json();
  return {ok: true, json: async () => value};
}
"""
    analysis = (directory / "analysis.js").read_text()
    analysis = re.sub(r"\bexport (?=const |function )", "", analysis)
    app = (directory / "app.js").read_text()
    app, imports = re.subn(r"^import .*? from './analysis\.js';\s*", "", app, count=1)
    if imports != 1:
        raise ValueError("Frontend imports changed; update the Streamlit asset adapter.")
    app = app.replace("await fetch(", "await fetchAsset(")
    html = (directory / "index.html").read_text()
    html = html.replace('<link rel="stylesheet" href="style.css">',
                        "<style>" + (directory / "style.css").read_text() + "</style>")
    html = html.replace('<script src="assets/plotly.min.js"></script>',
                        script((directory / "assets/plotly.min.js").read_text()))
    html = html.replace('<script type="module" src="app.js"></script>',
                        script(loader + "\n" + analysis + "\n" + app))
    return html


def main():
    import streamlit as st

    st.set_page_config(page_title="LA Pricing Review · Visual Analytics",
                       page_icon="↗", layout="wide", initial_sidebar_state="collapsed")
    st.markdown("""<style>
      .block-container {padding: 0.5rem 0 0; max-width: 100%;}
      [data-testid="stHeader"] {background: transparent; height: 0;}
    </style>""", unsafe_allow_html=True)
    try:
        # Include every asset in the cache key so a deployment refresh cannot
        # leave the old frontend or evidence in memory.
        version = tuple((str(p.relative_to(SITE)), p.stat().st_mtime_ns, p.stat().st_size)
                        for p in sorted(SITE.rglob("*")) if p.is_file())

        @st.cache_data(show_spinner="Preparing dashboard…")
        def dashboard_html(asset_version):
            return build_dashboard()

        st.iframe(dashboard_html(version), height=1100,
                  alt="Los Angeles pricing review: filters, charts, comparison and review priorities")
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"Cannot load the visual dashboard: {exc}")
        st.info("Deploy the whole repository, including site/dist and its assets folder.")


if __name__ == "__main__":
    main()
