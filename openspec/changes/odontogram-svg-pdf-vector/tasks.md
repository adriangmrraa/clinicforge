# Tasks: Odontogram SVG PDF Vector Preservation

## Phase 1: Diagnose current rasterization issue

- [ ] 1.1 Generate PDF with sample odontogram data using current system: Use `digital_records_service.py` `generate_pdf()` with a known patient record containing odontogram data.
- [ ] 1.2 Analyze PDF with `mutool` (or `pdfinfo`, Adobe Acrobat) to detect rasterization: Run `mutool extract` on generated PDF and inspect extracted images; check if SVG content appears as raster images.
- [ ] 1.3 Document findings in `docs/odontogram-vector-analysis.md`: Note which SVG elements are rasterized, file size, PDF structure, and any suspicious CSS/attributes.

## Phase 2: Research WeasyPrint SVG support

- [ ] 2.1 Review WeasyPrint documentation (official docs, GitHub issues) for SVG rendering and vector support: Focus on versions >=54 and known limitations.
- [ ] 2.2 Identify attributes and CSS properties that trigger rasterization (e.g., `max-width: 100%`, `opacity`, `filter`, `clip-path`).
- [ ] 2.3 Check current WeasyPrint version in `requirements.txt` or `pyproject.toml` and verify compatibility with vector SVG.
- [ ] 2.4 Document recommendations in `docs/weasyprint-svg-guide.md` with specific adjustments needed for odontogram SVG.

## Phase 3: Adjust SVG/CSS for vector rendering

- [ ] 3.1 Modify `orchestrator_service/services/odontogram_svg.py`: Add explicit `width` and `height` attributes to root `<svg>` element, set `preserveAspectRatio="xMidYMid meet"`, ensure `viewBox` is present.
- [ ] 3.2 Review and adjust CSS in `orchestrator_service/templates/digital_records/base.html`: Remove any `max-width: 100%` or `width: 100%` on `.odontogram-container svg`; replace with fixed dimensions or `max-width: none`.
- [ ] 3.3 Ensure SVG uses vector-friendly styles: Replace `opacity` with solid fill colors, avoid CSS filters and blur effects, use vector strokes instead of dotted/dashed lines if possible.
- [ ] 3.4 Test SVG rendering in browser: Generate SVG via `odontogram_svg.generate_svg()` and open in Chrome/Firefox to verify visual correctness and no regression.
- [ ] 3.5 If needed, update `orchestrator_service/services/digital_records_service.py` PDF generation configuration: Ensure `optimize_images=False` and `vector=True` options are passed to WeasyPrint.

## Phase 4: Test vector preservation in PDF

- [ ] 4.1 Regenerate PDF with modified SVG using the same sample data from Phase 1.
- [ ] 4.2 Verify vector preservation using `mutool extract` and analysis tool: Confirm no raster images present; SVG content should be embedded as vector paths.
- [ ] 4.3 Check zoom clarity at 400% in PDF viewer (Adobe Acrobat, Foxit): Ensure odontogram edges remain sharp without pixelation.
- [ ] 4.4 Compare file size before/after changes: Record sizes in `docs/odontogram-vector-analysis.md`.
- [ ] 4.5 Ensure HTML display remains unchanged: Compare browser rendering of odontogram before and after adjustments (screenshot diff).
- [ ] 4.6 Create verification script `scripts/verify_vector_pdf.py` that automates detection of rasterized SVG in generated PDFs for future regression testing.

## Phase 5: Documentation and cleanup

- [ ] 5.1 Update `README.md` or relevant developer documentation with findings and required SVG best practices.
- [ ] 5.2 Remove any temporary debug files created during diagnosis.
- [ ] 5.3 Ensure all changes are committed with descriptive commit messages.