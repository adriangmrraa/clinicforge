# Delta for Digital Records — Editor Text Duplication Fix

## MODIFIED Requirements

### REQ-EDIT-01: Textarea State Management (Modified)

Editable sections MUST use a separate plain-text state (`Record<string, string>`) during editing. The textarea `value` MUST bind directly to this text state — NOT to `htmlToText(section.content)`. HTML conversion MUST happen only at save time.

(Previously: textarea value was `htmlToText(section.content)`, onChange called `textToHtml()` per keystroke, causing round-trip conversion that duplicated content)

#### Scenario: Type in editable section without duplication

- GIVEN user is editing an authorization request document
- WHEN user types "Dolor en molar inferior" in the Diagnóstico section
- THEN text appears exactly once, cursor stays in position
- AND no text duplication occurs

#### Scenario: Delete text in editable section

- GIVEN user is editing a section with existing text "Tratamiento Solicitado"
- WHEN user selects all text and presses Delete/Backspace
- THEN all text is removed, section shows empty textarea

#### Scenario: Multi-line text entry

- GIVEN user is editing the Diagnóstico section
- WHEN user types "Línea 1" then presses Enter then types "Línea 2"
- THEN textarea shows two lines with a line break between them

### REQ-EDIT-02: htmlToText Line Break Preservation (Modified)

`htmlToText()` MUST convert `<p>` tags and `<br>` tags to newline characters (`\n`). It MUST NOT collapse all content into a single line.

(Previously: used `.textContent` which strips all HTML structure including line breaks)

#### Scenario: Convert multi-paragraph HTML to text

- GIVEN section content is `<h3>Title</h3><div class="narrative"><p>Line 1</p><p>Line 2</p></div>`
- WHEN htmlToText() is called
- THEN returns `"Line 1\nLine 2"` (heading excluded, paragraphs as lines)

### REQ-EDIT-03: textToHtml Conversion at Save Time Only (Modified)

`textToHtml()` MUST only be called when the user clicks "Guardar", not on every keystroke. It MUST preserve the original heading from the section's HTML.

(Previously: called on every onChange event via handleSectionTextChange)

#### Scenario: Save preserves structure

- GIVEN user edited Diagnóstico to "Caries en pieza 46\nNecesita endodoncia"
- WHEN user clicks Guardar
- THEN HTML becomes `<h3>Diagnóstico</h3>\n<div class="narrative"><p>Caries en pieza 46</p>\n<p>Necesita endodoncia</p></div>`

#### Scenario: Edit→Save→Re-edit round-trip

- GIVEN user saved a section with "Line A\nLine B"
- WHEN user clicks Editar again
- THEN textarea shows "Line A\nLine B" (not "Line ALine B" collapsed)

### REQ-EDIT-04: Textarea Row Calculation

Textarea `rows` MUST be calculated from the plain text state (counting `\n`), not from `htmlToText(section.content)`.

#### Scenario: Textarea height matches content

- GIVEN section text has 5 lines
- WHEN editing view renders
- THEN textarea has at least 6 rows (lines + 1)

## ADDED Requirements

### REQ-422-FIX: Completed Appointments Query

The `/admin/appointments` endpoint MUST accept `status=completed` as a valid query parameter without returning 422.

#### Scenario: Fetch completed appointments

- GIVEN patient 175 has completed appointments
- WHEN GET /admin/appointments?patient_id=175&status=completed&limit=20
- THEN returns 200 with list of completed appointments (not 422)
