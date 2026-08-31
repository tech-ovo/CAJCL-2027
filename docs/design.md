# **Design**

Design the website as a contemporary editorial publication for the **California Junior Classical League (CAJCL)**, hosted by University High School for the 72nd State Convention, March 12–13, 2027. The visual identity should feel scholarly, youthful, confident, distinctly Californian, and human-designed. **CAJCL is the primary visual identity**, with University High School providing a secondary sense of place. Draw inspiration from classical scholarship, inscriptions, academic journals, and print publications through typography, proportion, grid, rules, and composition — not through literal ancient imagery or stereotypical "Classics" decoration.

Use an editorial, print-inspired art direction rather than a generic SaaS or event-template aesthetic. Prioritize strong typography, generous whitespace, intentional asymmetry, flexible grid compositions, thin rules, subtle borders, editorial labels and metadata, and clear visual hierarchy. Avoid repetitive card grids, excessive rounded containers, glassmorphism, gradients, glowing elements, decorative blobs, heavy shadows, generic centered hero sections, and overly symmetrical layouts. The design should feel art-directed and specific to CAJCL rather than like an AI-generated website template.

Above all, **do not make the website look like AI slop**. Every visual element must serve identity, hierarchy, navigation, readability, or atmosphere. If something exists only to look "fancy," remove it.

## The signature element: the *tabula*

Every page of this site ultimately exists to identify a person, a chapter, or an entry. Make that the memorable thing.

The **tabula** is a bordered metadata block used consistently anywhere the site identifies something: the delegate's credential on the printed sheet and in the portal header, the school header on the roster and invoice, the entry header on a competition record. It is a thin 1px rule box with a second hairline rule inset 3px on the top and bottom edges only (a restrained echo of inscriptional double-ruling), containing letterspaced small capitals for the label and the identifying value set in IBM Plex Mono.

```
┌──────────────────────────────────────┐
│══════════════════════════════════════│
│  D E L E G A T E                     │
│  Mary Beth de la Cruz                │
│  DEL-K7M2N-9PQ4Z          №  0147    │
│══════════════════════════════════════│
└──────────────────────────────────────┘
```

This is the one place to spend boldness. Everything around it stays quiet. Do not invent a second signature device.

Set convention dates in Roman numerals in metadata contexts only — `XII–XIII MARTII MMXXVII` in the masthead rail and on printed sheets — with Arabic numerals everywhere a person needs to act on a date (deadlines, form due dates, payment dates). This is the entire budget for classical flourish. There are no Greek temples, marble textures, laurel wreaths, Greek-key borders, columns, statues, faux parchment, or ornamental Latin anywhere else.

## Masthead and the theme

The convention theme is content, not decoration, and it earns exactly one privileged placement: the masthead epigraph.

> aequam mementō rēbus in arduīs servāre mentem
> *Remember to keep an even mind in adversity*
> Horace, *Odes* II.3.1–2

Set the Latin in Literata italic at display size, the translation beneath in IBM Plex Sans at small size, and the citation as letterspaced small capitals in slate. It appears on the public welcome page in full and as a single-line rail on interior pages.

Incidental Latin is permitted where it is doing real work — `salvē` greeting a delegate by name on their portal home, `bonam fortūnam` on a competition confirmation — but never as ornament and never more than once per page. If a Latin phrase could be deleted without the page losing meaning or warmth, delete it.

## Color

**CAJCL's purple and gold are the defining colors**, supported by University High's navy and Columbia blue. Ivory is the primary light background; gold is an accent used sparingly.

| Token | Hex | Role |
|---|---|---|
| `--ink` | `#102A56` | Navy. Body text, primary headings, dark panels |
| `--purple` | `#542C6B` | CAJCL purple. Primary brand, links, active states |
| `--gold` | `#D4A72C` | CAJCL gold. Accent rules, marks on dark, never body text on ivory |
| `--blue` | `#7BA6D8` | Columbia blue. Large decorative fields, dark-ground text |
| `--lavender` | `#D9CBE5` | Tints, table zebra, selected rows |
| `--ivory` | `#F8F5EE` | Primary page background |
| `--slate` | `#46515F` | Metadata, captions, secondary text |
| `--mist` | `#B9BEC6` | Hairline rules, input borders, disabled states, table dividers |
| `--white` | `#FFFFFF` | Panels, inputs, print |

`--mist` on ivory is **2.0:1** — it is a rule and border color only, never text, never a focus ring. It exists because the palette otherwise had exactly one neutral, which made both the table hierarchy and the grayscale print rule below impossible to satisfy.

**These contrast rules are hard constraints, not preferences.** They were measured, not guessed:

- Gold on ivory is **2.06:1**. It fails WCAG for text at every size and fails the 3:1 minimum for focus rings and other non-text indicators. Gold on ivory is permitted **only** for rules, borders, underline decorations, and large display glyphs that carry no information a reader must read.
- Columbia blue on ivory is **2.40:1**. Same restriction.
- Gold on navy is **6.30:1** and Columbia blue on navy is comfortable. Both are valid text colors **on dark grounds only**.
- Purple on ivory is **9.90:1** and navy on ivory is higher. These carry all text.
- **Focus rings are purple or navy, never gold.** 2px ring, 2px offset, always visible, never removed.
- Never use purple/blue gradients, or any gradient.
- Never encode information by color alone — payment status, form completion, and validation state each need a text label or glyph as well as a hue.

Write the palette once as CSS custom properties in a single `tokens.css`. No hex literals anywhere else in the codebase.

## Typography

**Literata** for headlines and body. **IBM Plex Sans** for labels, metadata, table headers, form labels, and UI chrome. **IBM Plex Mono** for access codes, delegate ID numbers, invoice line amounts, and anything a person will read aloud or transcribe. All three are OFL-licensed and must be **self-hosted as subset woff2 files in the repository** — no Google Fonts CDN, no third-party request, no external point of failure.

**The subset must explicitly include Latin Extended-A.** The theme requires `ā ē ī ō ū`, which default Latin-basic subsetting silently drops, producing tofu boxes in the masthead. Add a build step that renders the full theme string and **fails the build** if any glyph is missing. This check is not optional; it is the most likely way this site ships broken.

Use tabular figures (`font-variant-numeric: tabular-nums`) in every table, invoice, and count. Typography carries the identity, so set a deliberate scale with real weight contrast, but avoid oversized type used only for drama.

## Grid, layout, and mobile

Flexible 12-column desktop grid with generous gutters and varied column spans. Do not force every section into the same layout; let headings, supporting information, and metadata occupy different regions, creating asymmetry that reads as deliberate. Preserve editorial hierarchy on mobile rather than stacking desktop components — on narrow screens the metadata rail becomes a top strip, the tabula goes full-bleed, and tables become labelled row-groups rather than horizontally scrolling grids.

Keep the interface component-light. Structure comes from typography, spacing, borders, alignment, and color rather than cards. Thin 1px borders, 2–4px corner radius at most, compact rectangular buttons, clearly identifiable links. No pill-shaped controls, oversized rounded rectangles, heavy shadows, or unnecessary effects.

## Forms

Most of this site is forms. They are a first-class surface, not an afterthought.

Labels sit above inputs in IBM Plex Sans small caps, left-aligned to the input edge. Help text sits below the label, above the input, in slate — a person should read the guidance before the field, not after failing it. Required fields carry a text marker, not a red asterisk alone. Inputs are white with a 1px slate border, 2px radius, and generous internal padding; they grow to fill their grid column rather than sitting at an arbitrary fixed width.

Validate on blur and on submit, never on every keystroke. Error messages appear directly beneath the field in navy on a lavender tint with a text label — never color alone, never a floating toast for a field-level problem. Error copy states what happened and how to fix it: "Pick between one and three tests. You have four selected." Never "Invalid input."

Buttons: one primary action per screen in purple with white text, secondary actions as bordered ghost buttons, destructive actions in navy with a confirmation step that requires typing or an explicit second click. Button labels are active and specific — "Add 28 delegates," not "Submit" — and the label persists through the flow, so a button that says "Send invoice" produces a confirmation that says "Invoice sent."

## Tables and dashboards

The registration chair dashboard is a table of fifty schools; the sponsor roster is a table of thirty people. These need to be genuinely good, not styled generically.

Header row in Plex Sans small caps with a 1px navy rule beneath. Body rows separated by 1px `--mist` rules, not full borders and not alternating fills except where a lavender tint marks a selected or flagged row. Numbers right-aligned and tabular. Sortable columns carry a visible affordance and an `aria-sort` attribute. Sticky header on scroll. Row density compact enough that thirty rows fit without scrolling on a laptop.

Every table has a designed empty state that invites the next action ("No delegates yet. Paste your roster to get started.") and a designed loading state — never a bare spinner, never an indefinite skeleton.

## The cold-start state

Because Modal scales to zero, the first request after an idle period takes several seconds. This is a designed state, not a failure.

Show an inline message in the content region — not a modal, not a full-page block — reading "Waking up the server…" after 400ms. After 8 seconds it becomes "This is taking longer than usual. Retrying…" with a manual retry control. After 20 seconds it becomes a clear failure message naming what a person should do instead: contact their sponsor, or `state@uhsjcl.org`. Never spin forever. Never show a blank page.

The public welcome page must render its convention facts and statistics from a build-time static snapshot immediately, then quietly replace them with live values when the API responds. A visitor arriving at a cold site sees a complete page, not a loading screen.

## Print

The printed instruction sheet, the packet cover, and the invoice are real deliverables that go in an envelope with a check.

**There is one implementation, not two.** The server renders a single HTML template per document. That same HTML is served to the browser as a print view *and* fed to WeasyPrint to produce the PDF — WeasyPrint is an HTML/CSS renderer, so the print stylesheet **is** the PDF stylesheet. Do not write a separate PDF layout, and do not treat the browser print view as a fallback for the PDF: both require Modal, because both need data that only Modal can supply. Building a second path would mean maintaining two things that fail together.

US Letter, 0.75in margins, 11pt body. Everything must be legible in **grayscale** on a school printer, so print styles map navy and purple to black, slate to a mid gray, and `--mist` to a light gray, dropping gold and Columbia blue entirely and relying on rule weight and type weight for hierarchy. Use `break-inside: avoid` on each attendee's block so no one's credential splits across pages, and `break-after: page` between attendees on the packet. Hide navigation, buttons, and the announcement banner. Print the convention contact address in the footer of every printed page.

## Imagery

**Do not generate, source, or place any stock photography, AI-generated classical imagery, campus photography, statues, temples, or placeholder imagery.** Every image on the finished site must be tied to CAJCL — real convention photography, real delegate work, the real CAJCL mark.

There is **no logo image on the site.** The available CAJCL mark is 216×184 and the NJCL mark belongs to a different organization. Ship a **type-only masthead**: "CAJCL" set in Literata with the convention line beneath it, with a reserved, correctly proportioned slot in the layout for the real vector mark when it arrives. Given the brief's thesis that typography carries the identity, this is the stronger choice regardless.

Image regions elsewhere may be represented by intentionally empty space or a flat lavender field with a label naming what will go there. The absence of imagery must not make the design feel unfinished.

## Motion and accessibility

Keep motion subtle and purposeful. No animated gradients, parallax, marquees, decorative animation, or hover effects beyond a state change. Transitions are 120–160ms on color and border only. Respect `prefers-reduced-motion` by disabling all transitions.

Semantic HTML throughout: real `<table>`, real `<label>` bound to inputs, real `<button>`, real landmark regions, one `<h1>` per page and no skipped heading levels. Every interactive element reachable and operable by keyboard with a visible focus ring. Form errors associated to their inputs with `aria-describedby` and announced via a polite live region. Target sizes at least 44×44px on touch — many delegates are eleven years old on a shared phone.

## Reuse

This site will be inherited. All brand tokens live in one `tokens.css`. All convention facts — year, ordinal, dates, venue, address, theme, translation, citation, contact address, fee amounts, deadlines — live in the `settings` table and are **editable from the admin dashboard**, not in a JSON file and not in code. A future commissioner should be able to run the 73rd convention by editing rows in a web form.

No dark mode. It is out of scope and would double the contrast-audit surface for no benefit to this audience.
