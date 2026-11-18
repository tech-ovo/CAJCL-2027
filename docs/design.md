# Design System & Brand Art Direction Specification

**Platform:** 72nd Annual CAJCL State Convention Platform (`state.uhsjcl.org`)  
**Host Venue:** University High School, Irvine (March 12–13, 2027)  
**Document Classification:** Design System & Art Direction Standard  

---

## 1. Design Philosophy & Creative Direction

The platform visual identity presents a contemporary, editorial publication honoring the **California Junior Classical League (CAJCL)**. It avoids the generic aesthetic of modern SaaS platforms and AI-generated event templates.

### Core Visual Principles
- **Print-Inspired Editorial Structure:** Visual hierarchy relies on deliberate typography, generous whitespace, asymmetric column rhythms, and delicate hairline rules rather than card grids, drop shadows, or decorative blobs.
- **Restrained Classical Influence:** Inspiration stems from classical inscriptions and scholarly journals. Stereotypical classical cliches (marble textures, column graphics, faux parchment, laurel wreaths) are strictly prohibited.
- **Intentional Simplicity:** Visual elements exist strictly to enhance hierarchy, legibility, and navigation. Gratuitous UI ornament is eliminated.

---

## 2. Signature Visual Element: The *Tabula*

Every core entity across the platform (attendee, chapter, contest submission) is anchored by a standardized metadata frame termed the **Tabula**:

```text
┌────────────────────────────────────────────────────────┐
│════════════════════════════════════════════════════════│
│  D E L E G A T E                                       │
│  Mary Beth de la Cruz                                  │
│  DEL-K7M2N-9PQ4Z                            №  0147    │
│════════════════════════════════════════════════════════│
└────────────────────────────────────────────────────────┘
```

- **Geometry:** 1px solid outer border with a recessed 1px hairline rule inset 3px on top and bottom edges (echoing classical inscriptional double-ruling).
- **Typography:** Classification labels rendered in letterspaced small capitals; entity titles set in Literata; cryptographic login tokens and badge coordinates set in IBM Plex Mono.
- **Usage:** Placed on printed attendee credential packets, portal credential headers, roster summaries, and formal competition invoices.

---

## 3. Masthead & Theme Typography

The convention theme represents substantive content rather than decoration, occupying a single dedicated masthead placement:

> *aequam mementō rēbus in arduīs servāre mentem*  
> **Remember to keep an even mind in adversity**  
> Horace, *Odes* II.3.1–2  

- **Latin Verse:** Set in Literata italic display weight.
- **English Translation:** Set in IBM Plex Sans regular text weight.
- **Citation:** Set in letterspaced small capitals in slate gray.
- **Display Scope:** Displayed in full on the public welcome page; rendered as a condensed single-line rail on authenticated interior screens.

---

## 4. Color Palette & WCAG Accessibility Governance

The color hierarchy bridges CAJCL’s traditional purple and gold with University High School’s navy and Columbia blue.

| Design Token | Hex Code | Visual Role | Contrast Ratio & Accessibility Rules |
| :--- | :--- | :--- | :--- |
| `--ink` | `#102A56` | Primary navy. Body text, primary headings. | **13.5:1** on ivory (WCAG AAA compliant). |
| `--purple` | `#542C6B` | Brand purple. Primary actions, links, active tab rules. | **9.9:1** on ivory (WCAG AAA compliant). |
| `--gold` | `#D4A72C` | Brand gold. Accent rules, dark-ground badges. | **2.06:1** on ivory (**Never use for text or focus rings on light backgrounds**). Valid on navy ground (**6.3:1**). |
| `--blue` | `#7BA6D8` | Columbia blue. Large decorative fields, dark-ground text. | Valid text color on dark navy ground only. |
| `--lavender`| `#D9CBE5` | Light purple tint. Row selections, error summaries. | Structural background tint. |
| `--ivory` | `#F8F5EE` | Primary application canvas background. | Base canvas neutral. |
| `--slate` | `#46515F` | Secondary text, captions, metadata labels. | **5.4:1** on ivory (WCAG AA compliant). |
| `--mist` | `#B9BEC6` | Hairline dividing rules, disabled controls. | Rule and border color only. Never used for text. |
| `--white` | `#FFFFFF` | Form input surfaces, print sheet canvas. | Surface neutral. |

### Color Usage Guardrails
1. **Never Encode Status by Color Alone:** Every validation state, payment status, and registration flag must pair color with explicit text labels or clear iconography.
2. **Deterministic Focus Rings:** Focus rings must render in `--purple` or `--ink` with 2px width and 2px offset; gold focus rings are prohibited due to contrast failures.
3. **Zero Gradients:** Gradients are strictly forbidden across all layouts and controls.

---

## 5. Typography Specification & Glyphic Integrity

| Font Family | Typographic Scope | Licensing & Delivery |
| :--- | :--- | :--- |
| **Literata** | Editorial headings, body copy, masthead quotes. | OFL, self-hosted WOFF2 |
| **IBM Plex Sans** | Form labels, UI chrome, navigation, table headers. | OFL, self-hosted WOFF2 |
| **IBM Plex Mono** | Login tokens, IDs, monetary currency, tabular stats. | OFL, self-hosted WOFF2 |

### Latin Extended-A Subsetting Constraint
- Convention copy requires Latin macrons: `ā ē ī ō ū`.
- Default Latin-basic webfont subsets silently drop macrons, producing rendering defects. Build tooling (`scripts/build_fonts.py`) validates font subsets against the full theme vocabulary, failing CI if any Latin Extended-A glyphs are missing.
- All monetary and tabular numeric columns enforce tabular figures: `font-variant-numeric: tabular-nums`.

---

## 6. Layout Grid, Forms & Component Patterns

### Grid Architecture
- **Desktop:** 12-column asymmetric grid with deliberate column spans to establish editorial pacing.
- **Mobile Reflow:** Fluid single-column responsive reflow. Metadata rails collapse into top strips; wide data tables convert into labeled block summaries.
- **Component Geometry:** Sharp, compact form language. Border radii constrained to 2–4px maximum. Rounded pill-buttons and heavy drop shadows are eliminated.

### Form Design Patterns
- **Label Alignment:** Labels sit directly above form inputs in IBM Plex Sans small capitals.
- **Guidance Text:** Instructional copy resides between the label and the input, ensuring users read guidance prior to field entry.
- **Validation Timing:** Fields validate on `blur` and `submit` (never on every keystroke). Error copy displays directly beneath inputs within a lavender tint container, providing active remediation instructions (e.g., *"Select between 1 and 3 academic tests; 4 currently selected"*).
- **Action Hierarchy:** Exactly one primary button per screen (`--purple` with white text). Secondary actions use ghost borders; destructive actions enforce explicit confirmation dialogs.

---

## 7. High-Density Tables & Dashboard Patterns

- **Roster & School Directories:** Engineered for compact vertical density to present 30–50 rows without excessive laptop scrolling.
- **Header Structure:** Small-cap headers anchored by a 1px solid navy bottom rule. Sticky position maintained during vertical page scrolling.
- **Row Separation:** Subtle 1px `--mist` horizontal hairline rules. Alternating zebra stripes are prohibited; selection states indicated via delicate lavender background fills.
- **Designed Empty States:** Screens lacking data present actionable next steps (e.g., *"No delegates registered yet. Click 'Paste Roster' to import your attendee list"*).

---

## 8. Serverless Latency & Cold-Start UX States

To accommodate Modal’s serverless scale-to-zero compute:
1. **Pre-Baked Static Baseline:** The public homepage immediately renders build-time static statistics baked into `index.html` via `build_snapshot.py`, ensuring instantaneous first-paint without waiting for API compute.
2. **Progressive Inline Telemetry:**
   - **0–400ms:** Standard responsive interaction.
   - **400ms–8s:** Subtle inline indicator: *"Waking convention service..."*
   - **8s–20s:** Updated message: *"Service initializing; retrying connection..."* with manual retry button.
   - **>20s:** Actionable diagnostic failure notice providing contact links (`state@uhsjcl.org`).

---

## 9. Unified Print & PDF Rendering Architecture

A single HTML template generates both physical browser print views and server-rendered PDF downloads:

- **Single-Source Rule:** The browser print stylesheet **is** the WeasyPrint PDF stylesheet. No parallel layout engines exist.
- **Paper Dimensions & Margins:** US Letter (8.5 × 11 in) with 0.75 in page margins.
- **Grayscale Conversion:** Colors automatically map to high-contrast grayscale: `--ink` and `--purple` map to pure black; `--slate` maps to 50% mid-gray; decorative gold and blue accents drop entirely.
- **Page-Break Protection:** Every attendee credential block enforces `break-inside: avoid`. Multi-attendee packets enforce `break-after: page` between registrants.
