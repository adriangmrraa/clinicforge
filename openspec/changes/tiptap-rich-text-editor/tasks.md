# Tasks: TipTap Rich Text Editor

## Phase 1: Install TipTap packages (Foundation)

- [ ] 1.1 Install @tiptap/react, @tiptap/pm, @tiptap/starter‑kit, and required extensions (bold, italic, underline, bullet‑list, ordered‑list, link) via npm
- [ ] 1.2 Update package.json and package‑lock.json; verify dependencies are added under "dependencies"

## Phase 2: Create reusable TipTap component (Core Implementation)

- [ ] 2.1 Create `frontend_react/src/components/RichTextEditor.tsx` with basic TipTap editor setup (useEditor, extensions, state)
- [ ] 2.2 Add toolbar component with buttons for bold, italic, underline, bullet list, ordered list, and link
- [ ] 2.3 Integrate DOMPurify sanitization in the `onChange` callback to sanitize HTML before emitting
- [ ] 2.4 Implement props interface: `value` (HTML string), `onChange` (callback with sanitized HTML), `placeholder`, `disabled`
- [ ] 2.5 Style editor container and toolbar to match dark theme (bg‑[#0a0e1a], border white/8, rounded‑lg, etc.)
- [ ] 2.6 Add unit test file `RichTextEditor.test.tsx` verifying rendering, formatting, and sanitization

## Phase 3: Integrate in ClinicsView.tsx FAQ answer field (Integration)

- [ ] 3.1 Replace textarea in add FAQ modal (line ~1130) with `<RichTextEditor value={faqForm.answer} onChange={(html) => setFaqForm({...faqForm, answer: html})} />`
- [ ] 3.2 Replace textarea in edit FAQ modal (line ~1255) with the same RichTextEditor component
- [ ] 3.3 Ensure FAQ list rendering (`faq.answer`) uses `dangerouslySetInnerHTML` with DOMPurify sanitization
- [ ] 3.4 Add helper function `sanitizeHtml(html: string): string` using DOMPurify in ClinicsView utils
- [ ] 3.5 Handle plain text existing answers: if answer contains no HTML tags, render with `white‑space: pre‑line` (or convert to HTML with `<p>` and `<br>`)

## Phase 4: Test and verify (Testing)

- [ ] 4.1 Test adding new FAQ with formatted answer (bold, italic, lists) and verify saved HTML contains correct tags
- [ ] 4.2 Test editing existing plain‑text FAQ, apply formatting, save, and verify updated answer is HTML
- [ ] 4.3 Verify XSS protection: try injecting `<script>alert('xss')</script>` and confirm script is removed
- [ ] 4.4 Verify UI consistency: editor matches modal styling, toolbar visible on focus, responsive layout
- [ ] 4.5 Run existing tests to ensure no regression in ClinicsView functionality