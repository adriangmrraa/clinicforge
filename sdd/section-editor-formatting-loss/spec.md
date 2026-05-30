# Digital Records Section Editor Specification

## Purpose

Ensure formatting preservation in digital records section editor by replacing plain textarea with TipTap rich text editor, preserving HTML formatting (bold, italics, lists) during edit‑save cycles while maintaining security sanitization.

## Requirements

### Requirement: Rich Text Editor Integration

The system **MUST** replace plain textarea with TipTap rich text editor for editable sections in `DigitalRecordsTab`. The editor **SHALL** provide basic formatting toolbar (bold, italic, underline, bullet list, numbered list). The editor **MUST** accept HTML input and output sanitized HTML.

#### Scenario: Editing a section with existing formatting

- GIVEN a digital record with an editable section containing HTML formatting (bold, italics, lists)
- WHEN the user enters edit mode
- THEN the section **MUST** be displayed in the rich text editor preserving original formatting
- AND the user **MUST** be able to apply new formatting via the toolbar
- AND the editor **SHALL** output sanitized HTML

#### Scenario: Saving formatted content

- GIVEN a user has modified formatting in an editable section using the rich text editor
- WHEN the user saves the record
- THEN the system **MUST** preserve all formatting in the saved HTML content
- AND the preview **MUST** display the formatted content correctly after saving

### Requirement: Formatting Preservation

The system **MUST** preserve HTML formatting (bold, italic, underline, lists, links) during the edit‑save cycle. Formatting **SHALL NOT** be lost or altered when converting between editor state and stored HTML.

#### Scenario: Bold and italic formatting

- GIVEN an editable section with bold and italic text
- WHEN the user saves and reopens the record
- THEN the bold and italic formatting **MUST** be preserved exactly

#### Scenario: Lists preservation

- GIVEN an editable section with ordered or unordered lists
- WHEN the user saves and reopens the record
- THEN the list structure **MUST** be preserved (list type, nesting, item count)

#### Scenario: Mixed formatting and plain text

- GIVEN an editable section containing a mix of formatted and plain text
- WHEN the user saves and reopens the record
- THEN the formatting **SHALL** be preserved only where originally applied
- AND plain text segments **SHALL** remain unchanged

### Requirement: Security Sanitization

The system **MUST** continue to use DOMPurify sanitization for security. All HTML content from the rich text editor **SHALL** be sanitized before being stored or displayed in preview.

#### Scenario: Malicious HTML input

- GIVEN a user attempts to inject script tags or event handlers via the rich text editor
- WHEN the content is saved
- THEN the system **MUST** sanitize the HTML removing unsafe tags and attributes
- AND the sanitized HTML **SHALL** be stored

#### Scenario: Safe HTML tags

- GIVEN a user inserts allowed formatting tags (strong, em, ul, ol, li, a, etc.)
- WHEN the content is saved
- THEN the allowed tags **SHALL** be retained after sanitization

### Requirement: Non‑editable Sections

The system **MUST NOT** allow editing of non‑editable sections. Sections marked with `data‑editable="false"` **SHALL** remain read‑only.

#### Scenario: Non‑editable section display

- GIVEN a section with `data‑editable="false"`
- WHEN in edit mode
- THEN the section **MUST** be displayed as read‑only (no editor)
- AND the content **SHALL** be rendered with DOMPurify sanitization

### Requirement: Backward Compatibility

The system **MUST** maintain existing section parsing and rebuilding logic (`parseSections`, `rebuildHtml`). Existing digital records without formatting **SHALL** continue to work unchanged.

#### Scenario: Existing records without formatting

- GIVEN an existing digital record with plain text sections (no HTML formatting)
- WHEN opened in edit mode
- THEN the rich text editor **MUST** display plain text correctly
- AND saving **SHALL NOT** corrupt the content or introduce unintended HTML

#### Scenario: Section parsing unchanged

- GIVEN any digital record HTML with `data‑section` attributes
- WHEN the record is loaded
- THEN the section parsing **MUST** produce the same sections as before
- AND editable flags **SHALL** be respected

### Requirement: Mobile Responsiveness

The rich text editor toolbar **MUST** be responsive on mobile devices. Editing functionality **SHALL** remain usable on screens as narrow as 320px.

#### Scenario: Mobile editing

- GIVEN the editor is viewed on a mobile screen (width < 768px)
- WHEN the user interacts with the toolbar
- THEN the toolbar **MUST** adapt to screen size (e.g., wrap, scroll, or collapse)
- AND editing **MUST** be fully functional

### Requirement: Bundle Size Impact

The addition of TipTap libraries **MUST NOT** increase the frontend bundle size beyond 50 KB (gzipped). Only necessary extensions **SHALL** be included.

#### Scenario: Bundle size check

- GIVEN the new dependencies are installed
- WHEN the production bundle is built
- THEN the total size increase **SHALL** be less than 50 KB gzipped

## Out of Scope

- Adding advanced formatting tools (images, tables, media)
- Changing backend API or database schema
- Editing non‑editable sections (patient data, generated content)
- Modifying other textareas in the system (clinical notes, etc.)

## Acceptance Criteria

1. Editable sections display formatted text (bold, italics, lists) correctly in the rich text editor
2. Formatting is preserved after saving and reopening the record
3. Non‑editable sections remain read‑only and unchanged
4. No regression in section parsing or preview functionality
5. HTML sanitization removes unsafe tags while preserving allowed formatting
6. Editor toolbar is usable on mobile devices
7. Bundle size increase < 50 KB gzipped