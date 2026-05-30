# Odontogram SVG Specification

## Purpose

Defines requirements for odontogram SVG generation and rendering in PDF documents, ensuring vector graphics preservation for high-quality print output.

## Requirements

### Requirement: Vector Preservation

The odontogram SVG MUST be embedded as vector graphics in PDF output, not rasterized.

#### Scenario: Vector detection

- GIVEN a generated PDF containing an odontogram SVG
- WHEN the PDF is analyzed with a vector detection tool (e.g., Adobe Acrobat Pro, mutool)
- THEN the SVG content MUST be identified as vector paths, not raster images.

#### Scenario: Zoom clarity

- GIVEN a PDF viewer displaying the odontogram
- WHEN the user zooms to 400% magnification
- THEN the odontogram edges MUST remain sharp without pixelation.

### Requirement: SVG Attributes

SVG markup MUST avoid attributes and CSS properties that trigger rasterization in WeasyPrint.

#### Scenario: Opacity handling

- GIVEN an SVG element with opacity styling
- WHEN the PDF is generated
- THEN the opacity MUST be preserved without converting the element to a raster image.

#### Scenario: Transform preservation

- GIVEN an SVG with transform (translate, scale) attributes
- WHEN the PDF is generated
- THEN the transforms MUST be applied as vector transformations, not rasterized.

### Requirement: WeasyPrint Configuration

The PDF generation configuration SHOULD be optimized for vector SVG rendering.

#### Scenario: WeasyPrint version compatibility

- GIVEN WeasyPrint version >= 54
- WHEN SVG vector support is available
- THEN the system MUST utilize vector rendering capabilities.

### Requirement: File Size

The PDF file size SHOULD not increase significantly due to rasterization.

#### Scenario: Size comparison

- GIVEN an odontogram with 32 teeth
- WHEN PDF is generated with vector SVG
- THEN the file size MUST be comparable to or smaller than the rasterized version.

### Requirement: Backward Compatibility

Changes to SVG generation MUST NOT break existing HTML display of odontogram.

#### Scenario: HTML rendering

- GIVEN the same odontogram data
- WHEN rendered in a web browser
- THEN the SVG MUST display correctly with intended styling.

### Requirement: Diagnostic Capability

The system MUST provide a means to verify vector rendering in generated PDFs.

#### Scenario: PDF analysis

- GIVEN a recent PDF generation
- WHEN a developer runs a verification script
- THEN the script MUST output whether SVG content is vector or raster.

### Requirement: Edge Cases

The SVG MUST render correctly for empty odontogram data and all tooth states.

#### Scenario: Empty odontogram

- GIVEN no tooth data (empty odontogram)
- WHEN PDF is generated
- THEN the SVG MUST display placeholder text without rasterization.

#### Scenario: All tooth states

- GIVEN odontogram data containing all possible tooth states (healthy, caries, restoration, etc.)
- WHEN PDF is generated
- THEN each state's visual representation MUST remain vector.