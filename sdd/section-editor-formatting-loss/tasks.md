# Tasks: Section Editor Formatting Loss Fix

## Phase 1: Install TipTap Dependencies

- [ ] 1.1 Add TipTap packages to frontend_react/package.json: `@tiptap/react`, `@tiptap/core`, `@tiptap/starter-kit`, `@tiptap/extension-bold`, `@tiptap/extension-italic`, `@tiptap/extension-underline`, `@tiptap/extension-bullet-list`, `@tiptap/extension-ordered-list`, `@tiptap/extension-link`
- [ ] 1.2 Install dependencies via npm (run `npm install` in frontend_react directory)
- [ ] 1.3 Verify bundle size impact by building production bundle and checking gzipped size increase (<50 KB)

## Phase 2: Create TipTap Editor Component

- [ ] 2.1 Create new component file `frontend_react/src/components/RichTextEditor.tsx`
- [ ] 2.2 Implement basic editor with toolbar (bold, italic, underline, bullet list, ordered list)
- [ ] 2.3 Integrate DOMPurify sanitization for HTML input/output (sanitize before passing to editor and before saving)
- [ ] 2.4 Define component props: `value` (HTML string), `onChange` (callback with HTML), `placeholder` (string), `editable` (boolean, default true)
- [ ] 2.5 Ensure mobile responsiveness: toolbar wraps or scrolls horizontally on narrow screens (<768px)
- [ ] 2.6 Style editor to match existing textarea design (dark theme, border, background, text color, rounded corners)
- [ ] 2.7 Add placeholder support and empty state styling

## Phase 3: Integrate with Existing Form State

- [ ] 3.1 Replace textarea in `DigitalRecordsTab.tsx` (lines 315-320) with RichTextEditor for editable sections
- [ ] 3.2 Update `handleSectionTextChange` to accept HTML directly (no text-to-HTML conversion)
- [ ] 3.3 Remove `htmlToText` and `textToHtml` usage for editable sections (keep functions for backward compatibility)
- [ ] 3.4 Ensure HTML content is sanitized before passing to editor (use DOMPurify with allowed tags)
- [ ] 3.5 Update `parseSections` and `rebuildHtml` to preserve HTML formatting (ensure they don't strip tags)
- [ ] 3.6 Verify backward compatibility: plain text sections (no HTML) still display correctly in editor
- [ ] 3.7 Handle non-editable sections: continue using DOMPurify sanitized display (no editor)

## Phase 4: Test Formatting Preservation

- [ ] 4.1 Write unit tests for RichTextEditor component (Jest + React Testing Library) in `frontend_react/src/components/RichTextEditor.test.tsx`
- [ ] 4.2 Test sanitization: verify unsafe tags (script, event handlers) are removed, allowed formatting tags are kept
- [ ] 4.3 Integration test: simulate editing a section with formatting, saving, reloading, and verifying formatting preservation
- [ ] 4.4 Mobile responsiveness test: simulate narrow viewport and verify toolbar usability
- [ ] 4.5 Bundle size check: run production build and confirm total bundle size increase < 50 KB gzipped
- [ ] 4.6 End-to-end test (Cypress or similar) for editing flow (optional but recommended)

## Phase 5: Deploy

- [ ] 5.1 Build production bundle (`npm run build`) and verify no errors
- [ ] 5.2 Deploy to staging environment for QA (follow existing deployment process)
- [ ] 5.3 Run end-to-end tests on staging to confirm functionality
- [ ] 5.4 Deploy to production (if separate from staging; may be out of scope for tasks)
