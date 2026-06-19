"""
Views for the Ireland GHG Policy Impact Explorer.

The page is a single, self-contained HTML file (it inlines its own CSS and JS).
We read it from disk and return it verbatim, which deliberately bypasses
Django's template engine so the page's CSS/JS braces are never misinterpreted.

The one thing we inject is the emissions dataset: it is read from the editable
CSV at ``data/ghg_inventory.csv`` and spliced into two placeholders in the page
(``/*@INVENTORY@*/{}`` and ``/*@YEARS@*/[]``). Edit that CSV and reload the page
— the chart, indicator switcher, baseline, forecast and KPIs all recompute.
"""
import csv
import json
from pathlib import Path

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import feedback_store
from . import rasters

# explorer/views.py -> explorer -> <project root>
BASE_DIR = Path(__file__).resolve().parent.parent
_PAGE_PATH = Path(__file__).resolve().parent / "page" / "index.html"
_CSV_PATH = BASE_DIR / "data" / "ghg_inventory.csv"
_POLICIES_PATH = BASE_DIR / "data" / "policies.csv"


def _load_inventory(csv_path: Path):
    """
    Read the wide-format inventory CSV into the structure the page expects.

    Returns ``(real_data, years)`` where:
      * ``real_data`` maps each gas column header -> list of values (floats,
        or ``None`` for blank cells), aligned to ``years``.
      * ``years`` is the sorted list of integer years (the first CSV column).

    The gas column headers must match the keys used by the page's INDICATORS
    map (e.g. "All greenhouse gases", "CO2", "CH4 - (CO2 equivalent)", ...).
    """
    with csv_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        # First column is the year; everything after is a gas series.
        gas_cols = [h.strip() for h in header[1:]]
        rows = []
        for raw in reader:
            if not raw or all(cell.strip() == "" for cell in raw):
                continue  # skip blank lines
            if raw[0].strip().startswith("#"):
                continue  # allow comment rows
            year = int(float(raw[0].strip()))
            values = []
            for cell in raw[1:]:
                cell = cell.strip()
                values.append(None if cell == "" else float(cell))
            # pad short rows so every gas stays aligned
            while len(values) < len(gas_cols):
                values.append(None)
            rows.append((year, values))

    rows.sort(key=lambda r: r[0])  # ascending years; arrays stay aligned
    years = [year for year, _ in rows]
    real_data = {
        gas: [vals[i] for _, vals in rows]
        for i, gas in enumerate(gas_cols)
    }
    return real_data, years


def _load_policies(csv_path: Path):
    """
    Read the climate-policy timeline CSV into a list of dicts.

    Expected columns: year, name, level, agency, sector, type, instrument,
    description, direction, outcome. ``level`` is one of International / EU /
    National / Target and drives the colour and the sidebar checkboxes.
    """
    policies = []
    with csv_path.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            year_raw = (row.get("year") or "").strip()
            if not year_raw or year_raw.startswith("#"):
                continue
            policy = {k: (v or "").strip() for k, v in row.items()}
            policy["year"] = int(float(year_raw))
            policies.append(policy)
    policies.sort(key=lambda p: p["year"])
    return policies


def _render_page():
    """Read the page and splice in the inventory data from the CSV."""
    html = _PAGE_PATH.read_text(encoding="utf-8")
    try:
        real_data, years = _load_inventory(_CSV_PATH)
        inventory_json = json.dumps(real_data, ensure_ascii=False)
        years_json = json.dumps(years)
    except FileNotFoundError:
        # No dataset present: serve the page with an empty (but valid) dataset.
        inventory_json, years_json = "{}", "[]"

    try:
        policies_json = json.dumps(_load_policies(_POLICIES_PATH), ensure_ascii=False)
    except FileNotFoundError:
        policies_json = "[]"

    html = html.replace("/*@INVENTORY@*/{}", inventory_json, 1)
    html = html.replace("/*@YEARS@*/[]", years_json, 1)
    html = html.replace("/*@POLICIES@*/[]", policies_json, 1)
    return html


def index(request):
    """Serve the Explorer single-page application with live CSV data."""
    return HttpResponse(_render_page())


# ---------------------------------------------------------------------------
# Raster overlay endpoints
# ---------------------------------------------------------------------------
def raster_catalog(request):
    """
    Return the nested raster catalogue that drives the cascading dropdowns::

        { "2019": { "B_Industry": { "pbenzoA": "2019_B_Industry_pbenzoA.tif" } } }

    The folder is re-scanned on every call, so files added to ``data/Raster``
    appear automatically with no code change or server restart.
    """
    return JsonResponse({"catalog": rasters.scan_catalog()})


def _resolve_selection(request):
    """Shared helper: pull year/sector/parameter from the query string."""
    year = (request.GET.get("year") or "").strip()
    sector = (request.GET.get("sector") or "").strip()
    parameter = (request.GET.get("parameter") or "").strip()
    if not (year and sector and parameter):
        return None, JsonResponse(
            {"ok": False, "detail": "year, sector and parameter are required."},
            status=400,
        )
    path = rasters.resolve_path(year, sector, parameter)
    if path is None:
        return None, JsonResponse(
            {"ok": False, "detail": "Unknown raster selection."}, status=404
        )
    return path, None


def raster_meta(request):
    """
    Return overlay metadata (WGS84 bounds, value range, colour stops, all-zero
    flag) for a selected raster — everything the page needs to place the image
    and draw the matching colour-bar legend.
    """
    path, error = _resolve_selection(request)
    if error is not None:
        return error
    try:
        r = rasters.render(path)
    except rasters.RasterRenderingUnavailable:
        return JsonResponse(
            {"ok": False, "detail": "Raster overlays are unavailable in this deployment."},
            status=503,
        )
    return JsonResponse(
        {
            "ok": True,
            "bounds": r["bounds"],
            "vmin": r["vmin"],
            "vmax": r["vmax"],
            "data_min": r.get("data_min", r["vmin"]),
            "data_max": r.get("data_max", r["vmax"]),
            "scale": r.get("scale", "linear"),
            "all_zero": r["all_zero"],
            "stops": r["stops"],
        }
    )


def raster_image(request):
    """
    Return the selected raster rendered as an RGBA PNG (rainbow colour map,
    zero/nodata transparent) for use as a Leaflet image overlay.
    """
    path, error = _resolve_selection(request)
    if error is not None:
        return error
    try:
        r = rasters.render(path)
    except rasters.RasterRenderingUnavailable:
        return JsonResponse(
            {"ok": False, "detail": "Raster overlays are unavailable in this deployment."},
            status=503,
        )
    resp = HttpResponse(r["png"], content_type="image/png")
    resp["Cache-Control"] = "public, max-age=3600"
    return resp


# ---------------------------------------------------------------------------
# Feedback endpoints
# ---------------------------------------------------------------------------
@csrf_exempt
@require_POST
def submit_feedback(request):
    """
    Accept a feedback submission (JSON or form-encoded) and persist it to the
    Excel workbook — committing to GitHub when configured, otherwise to local
    disk. Returns a small JSON status the front-end uses to confirm.
    """
    try:
        if request.content_type and "application/json" in request.content_type:
            data = json.loads(request.body.decode("utf-8") or "{}")
        else:
            data = request.POST.dict()
    except (ValueError, UnicodeDecodeError):
        return JsonResponse(
            {"ok": False, "detail": "Could not parse the submission."}, status=400
        )

    result = feedback_store.save_feedback(data)
    return JsonResponse(result, status=200 if result.get("ok") else 500)


def download_feedback(request):
    """
    Stream the current feedback workbook as an .xlsx download.

    Source of truth is GitHub when a token is configured, otherwise the local
    file. Useful as an admin convenience; the canonical copy also lives in the
    GitHub repo and can be downloaded directly from there.
    """
    content = feedback_store.get_workbook_bytes()
    if content is None:
        return HttpResponse(
            "No feedback has been recorded yet.",
            status=404,
            content_type="text/plain",
        )
    resp = HttpResponse(
        content,
        content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )
    resp["Content-Disposition"] = 'attachment; filename="inpact_feedback.xlsx"'
    return resp
