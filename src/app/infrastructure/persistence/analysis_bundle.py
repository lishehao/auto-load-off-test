from __future__ import annotations

import hashlib
from html import escape
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
from typing import Any

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np
import scipy

from app.application.dto import SaveTarget
from app.application.use_cases.analyze_measurement import AnalysisResult
from app.domain.data_validation import validate_sweep_result
from app.infrastructure.persistence.measurement_exporter import MeasurementExporter


BOUNDARY = "Offline file analysis; no instruments connected; not live hardware validation"


def _declares_simulation(meta: dict[str, Any]) -> bool:
    return any(word in str(meta.get(key, "")).lower()
               for key in ("source", "demo_label", "validation_boundary")
               for word in ("mock", "fixture", "simulat"))


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_analysis_bundle(
    directory: Path,
    analysis: AnalysisResult,
    *,
    analysis_id: str,
    created_at: str,
    inputs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Write into a private staging directory; the caller publishes it only after success."""
    result = analysis.measurement
    input_provenance = {
        key: str(analysis.input_measurement.meta.get(key, ""))
        for key in ("source", "demo_label", "validation_boundary")
    }
    simulated = _declares_simulation(input_provenance)
    boundary = f"No hardware - simulated fixture. {BOUNDARY}" if simulated else BOUNDARY
    result.meta.update({"analysis_id": analysis_id, "validation_boundary": boundary,
                        "input_validation_boundary": input_provenance["validation_boundary"]})
    MeasurementExporter().export(result, None, SaveTarget(directory / "measurement"))
    _write_plot(directory / "bode.png", analysis)
    arrays = validate_sweep_result(result)
    reference = analysis.reference
    try:
        app_version = version("auto-load-off-test")
    except PackageNotFoundError:
        app_version = "0.1.0 (source checkout)"
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "status": "completed",
        "analysis_id": analysis_id,
        "created_at_utc": created_at,
        "tool": {"name": "auto-load-off-test", "version": app_version,
                 "numpy": np.__version__, "scipy": scipy.__version__},
        "live_hardware_used": False,
        "validation_boundary": boundary,
        "input_source_claim": str(result.meta.get("source", "unknown")),
        "input_provenance": input_provenance,
        "simulated_input_declared": simulated,
        "inputs": inputs,
        "options": {"dataset": analysis.options.dataset, "correction": analysis.options.correction,
                    "coverage": analysis.options.coverage},
        "reference_correction": result.meta["reference_correction"],
        "interpolation": result.meta["interpolation"],
        "reference": None if reference is None else {
            "point_count": int(reference.freq_hz.size),
            "min_hz": float(reference.freq_hz[0]), "max_hz": float(reference.freq_hz[-1]),
            "has_phase": reference.phase_deg is not None,
            "outside_count": analysis.outside_reference_count,
        },
        "summary": {"point_count": len(result.points), "min_hz": float(arrays.freq_hz[0]),
                    "max_hz": float(arrays.freq_hz[-1]), "min_gain_db": float(np.min(arrays.gain_db)),
                    "max_gain_db": float(np.max(arrays.gain_db)),
                    "phase_point_count": 0 if arrays.phase_deg is None else int(np.isfinite(arrays.phase_deg).sum())},
        "warnings": list(analysis.warnings),
        "artifacts": [],
    }
    filenames = ["measurement.mat", "measurement.csv", "measurement.txt", "bode.png", "report.html"]
    manifest["artifacts"] = [{"path": name} for name in filenames]
    (directory / "report.html").write_text(_report_html(manifest), encoding="utf-8")
    manifest["artifacts"] = [
        {"path": name, "bytes": (directory / name).stat().st_size, "sha256": file_digest(directory / name)}
        for name in filenames
    ]
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    return manifest


def _write_plot(path: Path, analysis: AnalysisResult) -> None:
    original = validate_sweep_result(analysis.input_measurement)
    result = validate_sweep_result(analysis.measurement)
    has_phase = result.phase_deg is not None
    figure = Figure(figsize=(10, 6.5), dpi=140, layout="constrained")
    FigureCanvasAgg(figure)
    axes = figure.subplots(2 if has_phase else 1, 1, squeeze=False).ravel()
    gain_axis = axes[0]
    if analysis.options.correction != "none":
        gain_axis.semilogx(original.freq_hz, original.gain_db, color="#687784", linestyle="--", label="Input")
    gain_axis.semilogx(result.freq_hz, result.gain_db, color="#146b5d", linewidth=1.8,
                      marker="." if len(result.freq_hz) < 150 else None, label="Analysis result")
    gain_axis.set_ylabel("Gain (dB)")
    label = ("No hardware - simulated fixture" if _declares_simulation(analysis.input_measurement.meta)
             else "Input acquisition source unverified")
    gain_axis.set_title(f"Frequency response | Offline analysis\n{label}", loc="left", fontsize=12)
    gain_axis.legend(loc="best")
    if has_phase:
        phase_axis = axes[1]
        if analysis.options.correction != "none":
            phase_axis.semilogx(original.freq_hz, original.phase_deg, color="#687784", linestyle="--", label="Input")
        phase_axis.semilogx(result.freq_hz, result.phase_deg, color="#a44734", linewidth=1.8, label="Analysis result")
        phase_axis.set_ylabel("Phase (deg)")
        phase_axis.legend(loc="best")
    for axis in axes:
        axis.grid(True, which="both", alpha=0.2)
        axis.set_xlabel("Frequency (Hz)")
    figure.savefig(path, dpi=140)
    figure.clear()


def _report_html(manifest: dict[str, Any]) -> str:
    summary = manifest["summary"]
    options = manifest["options"]
    label = ("No hardware - simulated fixture" if manifest["simulated_input_declared"]
             else "Offline analysis - acquisition source unverified")
    input_rows = "".join(
        f'<tr><td>{escape(item["role"])}</td><td>{escape(item["original_name"])}</td>'
        f'<td><a href="{escape(item["path"], quote=True)}">Input copy</a></td>'
        f'<td class="hash">{item["sha256"]}</td></tr>' for item in manifest["inputs"]
    )
    warnings = "".join(f"<li>{escape(item)}</li>" for item in manifest["warnings"])
    links = "".join(
        f'<li><a href="{escape(item["path"], quote=True)}">{escape(item["path"])}</a></li>'
        for item in manifest["artifacts"] if item["path"] != "report.html"
    )
    reference = manifest["reference"]
    reference_text = "Not applied"
    if reference is not None:
        reference_text = (f'{reference["point_count"]} points; {reference["min_hz"]:g} - {reference["max_hz"]:g} Hz; '
                          f'{reference["outside_count"]} edge-clamped points')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Auto-Load-off-Test | Analysis report</title>
<style>
body{{margin:0;background:#f3f5f6;color:#20282c;font:15px/1.55 system-ui,sans-serif}}
main{{max-width:1024px;margin:0 auto;padding:32px 24px 48px;background:#fff}}
header{{border-bottom:2px solid #146b5d;padding-bottom:20px}}h1{{font-size:27px;margin:6px 0}}
h2{{font-size:19px;margin-top:28px}}p{{margin:8px 0}}.label{{color:#85531c;font-weight:600}}
.muted{{color:#52616b}}.metrics{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:24px 0}}
.metrics strong{{display:block;font-size:21px;color:#146b5d}}img{{display:block;width:100%;height:auto}}
table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{text-align:left;padding:10px;border-bottom:1px solid #dce2e5}}
th{{background:#f3f5f6}}.hash{{font:11px/1.6 monospace;overflow-wrap:anywhere}}a{{color:#166b8b}}
ul.files{{display:flex;flex-wrap:wrap;gap:12px 24px;padding-left:18px}}code{{overflow-wrap:anywhere}}
.table-scroll{{overflow-x:auto}}@media(max-width:620px){{main{{padding:20px 14px}}.metrics{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media print{{body{{background:#fff}}main{{padding:0}}}}
</style></head><body><main>
<header><p class="muted">Auto-Load-off-Test / Measurement analysis</p><h1>Frequency response report</h1>
<p class="label">{label}</p><p class="muted">{escape(manifest["created_at_utc"])}</p></header>
<div class="metrics"><div><strong>{summary["point_count"]}</strong>Frequency points</div>
<div><strong>{summary["min_hz"]:g} - {summary["max_hz"]:g}</strong>Frequency range (Hz)</div>
<div><strong>{summary["min_gain_db"]:.3f} / {summary["max_gain_db"]:.3f}</strong>Observed gain min / max (dB)</div>
<div><strong>{summary["phase_point_count"]}</strong>Points with input phase</div></div>
<img src="bode.png" alt="Gain and available phase versus frequency; input and analysis result">
<h2>Processing record</h2><p>Dataset: <strong>{options["dataset"]}</strong>;
correction: <strong>{options["correction"]}</strong>; coverage policy: <strong>{options["coverage"]}</strong>.</p>
<p>Reference: {reference_text}. Interpolation: <code>{manifest["interpolation"]}</code>.</p>
<p>Input source claim: <code>{escape(manifest["input_source_claim"])}</code>. Run ID: <code>{manifest["analysis_id"]}</code>.</p>
<p>Input boundary statement: {escape(manifest["input_provenance"]["validation_boundary"] or "Not supplied")}.</p>
<h2>Notes</h2><ul>{warnings}</ul><p>{BOUNDARY}.</p>
<h2>Input provenance</h2><div class="table-scroll"><table><thead><tr><th>Role</th><th>Original filename</th>
<th>Snapshot</th><th>SHA-256</th></tr></thead><tbody>{input_rows}</tbody></table></div>
<h2>Artifacts</h2><ul class="files">{links}<li><a href="manifest.json">manifest.json</a></li></ul>
<p class="muted">Reproduce from the bundled input copies and processing options in manifest.json.
File hashes verify identity, not acquisition accuracy. Timestamps and MAT headers may differ on reruns.</p>
</main></body></html>'''
