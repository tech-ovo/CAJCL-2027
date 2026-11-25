# Open Questions & Ambiguities — 2027 CAJCL Convention Platform

**Context:** This document collects every question, ambiguity, and discrepancy identified when aligning the platform documentation and current codebase with the **2027 CAJCL Convention Book** (`docs/2027 CAJCL Convention Book .pdf`), the **2027 PDF registration forms**, and **CAJCL leadership's data/website guidelines email** (Mr. Muth & Mr. Davis).

Please work through these with collaborators and mark decisions inline so we can finalize the implementation and documentation before the **December 1, 2026** registration launch.

> **Update (Nov 24, 2026):** Decisions and status updates from Carl's planning notes (`docs/carl/notes.md`, `docs/carl/questions.md`) have been recorded inline below. Active implementation tasks are tracked in `docs/carl/todo.md`.

---

## 1. Registration Architecture & Parallel Google Sheet Path

1. **Will we offer a parallel Google Sheet registration option alongside the website?**
   - *Mr. Muth's email (Next Steps):* "decide whether to offer an alternative registration path through the website in addition to the Google Sheet method (we at least need to offer a familiar and tested option too)" — while also stating *"We must use a single system to house all registration data for the operational ease of future convention hosts."*
   - *Convention Book (Page 3):* Presents the website as the sole registration platform with no mention of a Google Sheet alternative.
   - **Question:** Are we committing to website-only registration (as printed in the Convention Book), or will sponsors who want a Google Sheet fill out a sheet that Registration Chairs manually import into the website so all data still lives in one database?

2. **How should "Adult Join Codes" work?**
   - *Convention Book (Page 3):* "The email also contains a chapter-specific Join Code sheet for students **and adults (SCL, Sponsors, Chaperones)** to complete activity sheets on the website."
   - *Current codebase:* `POST /auth/join` currently only creates **pending student delegates** (`DEL-`). It does not support adults joining via a join code.
   - **Question:**
     - Should `#/join` let someone choose whether they are a Student, Chaperone/Volunteer, Sponsor, or SCL?
     - Should adult self-registrations via join code also enter a "Waiting for approval" queue for the chapter's primary sponsor?
     - If an adult selects "Sponsor", should approving them automatically grant `sponsor` scope (allowing them to see the whole chapter roster), or should only Registration Chairs be able to grant `sponsor` privileges?
     - For SCL attendees: are SCL members joining under their own special SCL chapter (with its own Join Code), or under a high school chapter?

3. **Should we still support "Paste Roster" for sponsors?**
   - *Current codebase:* Supports both Join Codes and pasting a full roster of names.
   - *Convention Book (Page 3):* Only describes the Join Code workflow.
   - **Question:** Should we keep "Paste Roster" available on the Sponsor Roster page as a power-user option, or hide/de-emphasize it so sponsors follow the consent-gated Join Code flow?

4. **Locking student identity fields after initial entry:**
   - *Convention Book (Page 3):* "Once a student sets their name, grade, and Latin level, only the sponsor can change those details."
   - **Question:**
     - Should name, grade, and Latin level lock *immediately* upon joining (`POST /auth/join`) — even before the sponsor approves them — so a typo requires asking the sponsor to fix it?
     - What about middle name, suffix, and meal preference? Can students still edit their own meal preference up until February 13?

5. **What can a "Pending" (unapproved) student do on the website?**
   - *Current codebase:* Pending students can fill in their Activity Sheet immediately, but cannot sign up for Olympika and are excluded from invoices/counts until approved.
   - **Question:** Should pending students be allowed to submit Pre-Convention Contests or Activities Potluck picks before their sponsor approves them, or should those also wait for sponsor approval?

6. **How is the parental consent gate enforced before Join Code entry?**
   - *Convention Book (Page 3):* "As we may not collect student data without parental consent, only distribute Join Codes after waiver and medical have been submitted."
   - **Question:**
     - Is this enforced operationally by sponsors (only handing out the Join Code sheet after receiving paper forms), or should we also add a required confirmation checkbox on `#/join` (e.g., *"My parent/guardian has signed and turned in my CAJCL Waiver and Medical Form"*)?
     - Should the Sponsor's "Approve" button also require (or automatically check) "Paper waiver & medical received"?

7. **Multi-division schools (Middle School + High School):**
   - *Current codebase:* Schools sending both MS and HS delegations are modeled as two discrete chapters (two separate `school_id`s, two Join Codes, and one sponsor linked via `sponsor_school_grants`).
   - **Question:** Does that match how CAJCL Chapter Registration and invoicing expect MS/HS chapters to work? Will a sponsor with both MS and HS students receive two separate Join Code sheets?

8. **Lost Student Login Tokens (`DEL-XXXXX-XXXXX`):**
   - When a student joins via Join Code, they receive their personal login token once.
   - **Question:** If a student forgets/loses their token before February 13 (or at Convention for Photo Contest / Olympika), is the expected workflow simply "ask your sponsor to click Reissue Login Token"? Will printed name badges at Convention include a QR code or login token, or will name tags have no credentials on them?
   - **Partial Decision (Carl, Nov 24):** Name tags will print **name, school, grade/level, and volunteer assignments** (no QR code or login token). Lost-token workflow during convention remains to be confirmed with Registration Chairs.

---

## 2. Authentication, 2FA, Repository Privacy & Vendor Vetting

9. **Sponsor One-Time Code (2FA) specification:** `[OWNED BY SOMEONE ELSE — DEFERRED]`
   - *Convention Book (Page 3):* "To secure student data, sponsors will receive a one-time code each time they sign in."
   - **Status (Carl, Nov 24):** Another team member is handling 2FA and the email system for now (`state@uhsjcl.org` is already set up as a verified sender alias). Keep open for that owner to finalize:
     - Should the one-time code be sent via **email** (using Google Apps Script / official `cajcl.org` email) or another method?
     - Does 2FA apply **only** to `sponsor` accounts (`SPO-`), or also to chaperones (`VOL-`), SCL, contest judges, and/or administrative board roles (`admin`, `registration`, `academics`, `awards`, `activities`, `athletics`, `logistics`)?
     - Note: Some board officers (Convention Presidents, Registration Chairs, etc.) are students — do student board officers have an official `cajcl.org` / `uhsjcl.org` email address we can use for 2FA, or should admin 2FA use their board email?
     - How long should a sponsor's session stay signed in after entering the one-time code (e.g., 24 hours, 72 hours, 7 days, or until browser close)?
     - Have we tested whether school district email filters (e.g., IUSD, LAUSD, etc.) block automated OTP emails from our Apps Script sender address?

10. **Private GitHub Repository vs. GitHub Pages Hosting:**
    - *Mr. Muth's email:* "All code used for the website must not be publicly available, especially back-end server code (a private Github folder is fine, but not open to the public)."
    - *Technical constraint:* Free GitHub accounts do not allow GitHub Pages on a private repository (GitHub Pro/Team/Enterprise is required, OR we split deployment so the private repo holds all code and a separate public repo / Cloudflare Pages / Netlify hosts only the built static frontend HTML/CSS/JS).
    - **Question:** Which hosting setup should we use so all backend/source code stays strictly private while `state.uhsjcl.org` stays live? (Note: If we use Cloudflare Pages or Netlify, an adult leader must vet it first per Mr. Muth's vendor guideline.)

11. **Vendor Vetting & Third-Party Tools:**
    - *Mr. Muth's email:* "All websites we use that have access to student PII must not sell their data or advertise to students (I checked Modal and Turso and they are fine; we need an adult to check other sites or tools before using them)."
    - **Question:**
      - Has an adult leader formally reviewed and approved **GitHub** (hosting static frontend, zero PII) and **Google Workspace / Drive / Apps Script** (contest files, photo contest, 2FA emails, backup Google Sheet)?
      - Are we moving Google Drive / Apps Script off personal Gmail onto an official `cajcl.org` Google Workspace account before December 1?
      - The Convention Book and Student Activity Sheet mention **Blooket / Kahoot** (Percy Jackson) and **Goose Chase** (Scavenger Hunt). Will students use anonymous nicknames (zero PII) on those, or do those platforms need adult privacy vetting too?

12. **Official CAJCL Privacy Policy & Updated Waiver:** `[WAITING ON MR. MUTH]`
    - *Mr. Muth's email:* "Mr. Muth will update the language on the waiver and write a CAJCL Privacy Policy to link to in our registration materials (by 11/15)."
    - *Convention Book (Page 2 & 3):* Lists CAJCL Waiver as `COMING SOON!`.
    - **Decision / Status (Carl, Nov 24):** Mr. Muth is rewriting both the Privacy Policy and Student Waiver and will provide PDFs. Once received, we will replace the existing PDFs and expose download links in the site's **Documents / Resources** section. All leftover anonymization / ID-only references are being removed across the docs and site. Still confirm whether `#/privacy` should mirror or link directly to Mr. Muth's PDF.

13. **Student Personal Email & Guardian Contact Fields:**
    - *`2027 Student Activity Sheet.pdf`:* Has a blank line for **"Personal Email"**.
    - *Current database schema:* Refuses to store student emails (`CHECK` constraint), and collects `guardian_name` and `guardian_phone` on delegates.
    - **Question:**
      - Confirm we are **NOT** collecting student personal emails on the website (and should the "Personal Email" line be removed from the PDF too so nobody is confused)?
      - Should we still collect `guardian_name` and `guardian_phone` in the web database, or remove those fields from the online form since emergency contact info is already on the paper Medical Form?

14. **Public Homepage Content & Search Engine Indexing:**
    - *Mr. Muth's email:* "The public cannot see any student names/data (e.g., schedule/map only), and public links should not be shared widely (e.g., only in physical QR codes or emails to registered attendees, not social media)."
    - **Question:**
      - Is it still okay for the public welcome page (`#/`) to show aggregate numbers (e.g., total chapters, total delegates, total adults), or should we remove even aggregate counts from the public page?
      - Should we add `robots.txt` (`Disallow: /`) and `<meta name="robots" content="noindex, nofollow">` so the site doesn't appear in Google search results?

15. **Certamen Practice Arena (`certamen-bot/`) Privacy & Security:**
    - *Current state:* `certamen-bot/` has unauthenticated routes, plaintext PINs, and a chapter-only leaderboard (no individual names).
    - **Question:** Does the Certamen Practice Arena need to be hardened (PIN hashing, auth on question batch endpoints) before December 1, and does it store any student PII (e.g., if students type their real name as their Certamen username)? Should we warn students not to use their real name as a Certamen username?

---

## 3. Paperwork, Mailing, Fees, Discounts & Substitutions

16. **Check Payee Line:**
    - *Convention Book (Page 3):* `University High School c/o Mark Michalak, 4771 Campus Drive, Irvine, CA, 92612`
    - *Existing docs (`REGISTRATION.md`, `TERMS_OF_SERVICE.md`):* `University High School JCL c/o Mark Michalak`
    - **Question:** Which exact payee name should appear on generated website invoices so checks don't bounce or get rejected by the school bookkeeper?

17. **Check Arrival Notifications (Email + Website):** `[DEFERRED]`
    - *Convention Book (Page 3):* "Sponsors will be notified via email and on the website when the check arrives."
    - *Current codebase:* Recording a payment updates the website balance, but does **not** send an email.
    - **Status (Carl, Nov 24):** The automated email system is deferred for now. Current plan is to automate only a single manually-approved pre-deadline reminder (~2 weeks before 2/13) and send other emails manually (with a quick way to copy sponsor emails per school); confirm with Registration Chairs later whether check-arrival emails stay manual.

18. **New School 75% Discount:**
    - *Convention Book (Page 3):* "New School? Contact the Convention sponsors or presidents to receive 75% off!"
    - *Current codebase:* `schools.discount_cents` is a fixed dollar amount in cents (doesn't auto-scale when roster size changes).
    - **Question:**
      - Does 75% off apply to the **entire** chapter invoice (students + extra adults), or **student fees only**?
      - Should we add a `discount_percent` field (e.g., `75`) to `schools` so invoices automatically recalculate 75% off as students join/approve, or will Registration Chairs manually compute and enter `discount_cents` after February 13?

19. **Substitutions Workflow (February 13 → February 26, 2027):**
    - *Convention Book (Page 2 & 3):* Registration & activity sheets lock February 13; *"Make substitutions before February 26, 2027"*; *"If substitutions are made afterward, sponsors may either mail the updated forms to the same address or bring them during check-in."*
    - **Question:**
      - How should a substitution work on the website? Should sponsors be able to click **"Substitute"** on a student (which swaps the person in-place or cancels the old student and creates a replacement without double-charging), or must sponsors email `state@uhsjcl.org` to have Registration Chairs process substitutions?
      - **Billing edge case:** Currently, if a chapter has already paid and cancels Student A (`cancelled_paid`) and adds Student B (`active`), the invoice adds another $140! We need to make sure a 1-for-1 substitution before Feb 26 does **not** charge an extra $140. How should we model this in the database/ledger (e.g., a dedicated `substituted` status, or an automatic credit)?
      - Can a substituted student still submit/edit their Activity Sheet between February 13 and February 26?

20. **Paper-Only Waivers & Medical Forms (No Google Drive Scans):**
    - *Convention Book (Page 3):* "Unlike last year, we are NOT asking sponsors to scan each document and upload to Google Drive. The sponsor must ensure that the submitted documents match the website registration."
    - **Question:**
      - Should we remove all UI mentions of chapter Google Drive folders for paper forms?
      - Who checks off the `paper_forms` checkboxes (`student_waiver`, `student_medical`, `adult_medical`) on the website: the Sponsor (as an attestation before mailing), or the Registration Chairs (when opening the mailed envelope at University High School), or both?

21. **Chapter-Level Details ("meals requested", "event potluck sign-ups"):**
    - *Convention Book (Page 4, Sponsors Must Do Before):* "Input chapter details (e.g., event potluck sign-ups, meals requested)" and "Print attendee forms (sponsors must also submit forms!)."
    - **Question:**
      - Currently, meal preferences (`Regular`, `Vegetarian`, `Gluten-Free`) are entered per-person on each Student/Adult Activity Sheet. Does "meals requested" just mean reviewing/verifying the chapter's meal counts, or do sponsors also need to enter something at the chapter level?
      - For "event potluck sign-ups": is that the existing **Activities Potluck** (individual helpers signing up on their activity sheet, approved by the sponsor), or is there a **chapter-level** potluck sign-up (e.g., each chapter commits to running/bringing supplies for an activity)?

---

## 4. Contests, Deadlines & Event Catalog Discrepancies

22. **Per-Contest Deadlines (March 6 vs. March 13 at 10:00 AM):**
    - *Convention Book (Page 2 & 6):*
      - Pre-Convention Individual Contests (Digital Art/Poster, Latin Slogan, English Slogan, Modern Myth, Original Poetry), Scrapbook Pictures, and Publicity Portfolio: due **March 6, 2027** (presumably 11:59 PM PST?).
      - Digital Scrapbook: due **March 13, 2027 at 10:00 AM** PDT!
    - *Current codebase:* Only has a single global `deadline.contests` setting.
    - **Question:** Should we add per-contest deadlines in the `contests` table so Digital Scrapbook stays open until March 13 at 10:00 AM while all other pre-convention contests lock March 6 at 11:59 PM?

23. **Scrapbook Pictures & Digital Scrapbook Submissions:**
    - *Convention Book (Page 6):* Lists **Scrapbook** (submit pictures online by March 6 AND turn in physical scrapbook at Chapter Registration), **Digital Scrapbook** (due March 13 at 10 AM online), and **Publicity Portfolio** (due March 6 online).
    - **Question:**
      - Do we need to add Scrapbook Pictures and Digital Scrapbook to the `contests` catalog?
      - For Scrapbook Pictures, should chapters upload a single PDF/ZIP, a link, or multiple image files? (Current upload cap is 20 MB per file.)
      - For Digital Scrapbook, is it a file upload (PDF/PPTX) or a link (Google Slides / Canva / PDF)?

24. **Academic Testing Count Discrepancy (11 vs. 15):**
    - *Convention Book (Page 6):* Says **"Academic testing (11 tests)"**.
    - *`2027 Student Activity Sheet.pdf`:* Lists **15** checkboxes (Classical Art, Daily Life, Derivatives, Geography, Grammar 1, Grammar 2, Grammar 3, History, Mottos/Quotes/Abbrev., Mythology, Pentathlon, Reading Comp. 1, Reading Comp. 2, Reading Comp. 3, Vocabulary — which is 11 subjects if Grammar 1–3 and Reading Comp 1–3 are grouped, or 15 individual exams).
    - **Question:** Confirm the website catalog should keep all 15 level-filtered exam options (with the 1–3 test selection rule), and verify whether **Latin Composition Contest** (listed on Saturday 1:00 PM schedule, Page 9) should also be selectable on the Activity Sheet.

25. **Olympika Events Discrepancy:**
    - *Convention Book (Page 6 & 9–10):*
      - Individual: **Chess, Track and Field**
      - Team: **Basketball, Volleyball, Dodgeball (Fugepilam), Ultimate Frisbee**
    - *`2027 Student Activity Sheet.pdf`:*
      - Individual: **Chess, Track (100m, 200m, 400m)**
      - Team: **Kickball*, Ultimate Frisbee*, Fugepilam (Dodgeball)*** (NO Basketball or Volleyball; HAS Kickball!)
    - **Question:** Which exact set of Olympika events is final for 2027? (Should Kickball be replaced by Basketball & Volleyball in the website catalog and Activity Sheet PDF?)

26. **Ludi Events Discrepancy:**
    - *Convention Book (Page 7):*
      - New Ludi: Cooking Class, Streetamen, Midway Games, garum Games, Latin Word Games.
      - Returning Ludi: Blooket/Kahoot (Percy Jackson), Edible Mosaics, Karaoke, Open Certamen, Pandora's Breakout Box, Project Runway, Roman Rap Battle, Roman Speed Dating, Star Gazing, STEM Challenge, That's Entertainment!, Ōvō Vēnātiō (Scavenger Hunt), Costume.
    - *`2027 Student Activity Sheet.pdf`:* Still lists **Spelling Bee** and **Percy Jackson Kahoot** / **Scavenger Hunt (Goose Chase)**, and omits all 5 New Ludi + Karaoke + Star Gazing.
    - **Question:** Should the website's Activity Sheet catalog be updated to match the Convention Book Page 7 list? Which Ludi events actually require advance sign-up on the website vs. just showing up?

---

## 5. Website Features Listed in Convention Book Page 4 (Scope & Implementation)

The Summary Table on Page 4 of the Convention Book lists several features that are **not yet built** in the platform. For each one below, please confirm whether we should **(A) build it into `state.uhsjcl.org`**, **(B) link to an external tool/Google Doc**, or **(C) cut/defer it**:

27. **Interactive Campus Map** (*Everyone — During Convention:* "View interactive map/schedule"): `[DEFERRED — SEPARATE TRACK]`
    - Previously marked Out of Scope in `TODO.md`.
    - **Status (Carl, Nov 24):** Delegate convention frontend (including map/schedule experience) will be scoped and built separately once room assignments and the final schedule are ready.

28. **Personal Schedule Planner** (*Everyone — Before Convention:* "View and plan out a schedule"): `[DEFERRED — SEPARATE TRACK]`
    - Currently `#/schedule` displays the full master schedule, without a personal "star/bookmark" or "My Schedule" filter.
    - **Status (Carl, Nov 24):** Flagged as part of the separate delegate convention frontend track (TBD once schedule/rooms are finalized).

29. **Lost and Found** (*Everyone — During Convention*): `[RESOLVED]`
    - **Decision (Carl, Nov 24):** **Option B (Link)** — link out to an external form/sheet rather than building natively into the website.

30. **Candidate Statements** (*Everyone — During Convention*):
    - **Question:** Can candidate statements be published as a static text page from a Google Doc via **Site pages** (`#/site-pages`), or do candidates need a form to submit them on the website? (Reminder: check Mr. Muth's rule against putting student names on *public* pages — should Candidate Statements be behind login?)

31. **Submit Feedback** (*Everyone — During Convention*): `[RESOLVED]`
    - **Decision (Carl, Nov 24):** **Option B (Link)** — link out to an external Google Form rather than building an in-app feedback form.

32. **Pre-Convention Event Sign-Ups** (*Students Must Do Before:* "Sign-up for certain events (Open Certamen, Pandora's Breakout Box, Ludi/Olympika, That's Entertainment Auditions)"): `[PARTIALLY RESOLVED]`
    - **Decision (Carl, Nov 24):** ***That's Entertainment*** will be built in-app with **full audition sign-up and automatic scheduling that Activities Chairs can edit afterward** (judging flow is still TBD).
    - **Remaining Question:**
      - Do Open Certamen or Pandora's Breakout Box need specialized sign-up/team flows beyond Activity Sheet checkboxes?
      - Should Olympika sign-ups open *before* convention (as Page 4 implies under "Before Convention") or only *at* convention?

33. **Live Brackets for Open Certamen** (*Students — During Convention:* "Live brackets for certain events (Open Certamen, Olympika)"):
    - Currently only Olympika has a bracket engine (`#/athletics` / `#/olympika`).
    - **Question:** Does Open Certamen need live brackets on the website? If so, does it follow single-elimination (like Olympika) or multi-round point-ladder play? Who runs it (Certamen Chair Sophia Liu / Open Certamen Advisor Dobbie Vasquez)?

34. **At-Convention Interactive Events** (*Students — During Convention:* "Certain events (Scavenger Hunt, Percy Jackson Blooket, Graphic Arts Voting, Photo Contest, and more to be revealed)"):
    - Photo Contest (`#/photos`) is already built.
    - **Question:**
      - **Graphic Arts Voting:** Do we need to build an authenticated one-vote-per-delegate voting UI on the website, or will it use a separate form?
      - **Scavenger Hunt (Ōvō Vēnātiō) & Percy Jackson Blooket:** Are these just links/instructions on the website pointing to external tools, or is Scavenger Hunt being built into our site?
      - **"and more to be revealed":** Are there any other interactive events planned for the website that we should scope now?

35. **Volunteering Obligations View** (*Sponsors & Adults Must Do During Convention:* "View volunteering obligations"): `[RESOLVED]`
    - Currently, adults submit volunteer *preferences* on the Adult Registration Sheet, but there is no admin UI to assign shifts/rooms or an adult view showing their assigned shifts.
    - **Decision (Carl, Nov 24):** Build **in-app editing for volunteer assignments** and print each person's volunteer assignments on their **name tag** (alongside name, school, and grade/level).

36. **Sponsors Assigning Chapter Leaders:**
    - *Convention Book (Page 4, Sponsors May Do Before):* "Assign chapter leaders (e.g., to manage chapter contests or team registration)."
    - *Current codebase:* The `chapter_leader` role exists in the database, but only Admins can assign roles (`Settings → Roles`).
    - **Question:** Should we add a button on the Sponsor's Roster page allowing a Sponsor to promote/demote a student in their own chapter to `chapter_leader`?

37. **Sponsors Grading Pre-Convention Contests:**
    - *Convention Book (Page 4, Sponsors May Do Before):* "Grade pre-convention contests (if applicable)."
    - **Question:**
      - Can a Chapter Sponsor simultaneously hold the `judge` role (so they use their same `SPO-` login token to see a **Judging** tab)?
      - If a Sponsor judges a pre-convention contest, should the system automatically hide entries from their own chapter (`school_id`), or is double-blind (`Entry N`) sufficient?

38. **During-Convention Score Entry & Post-Convention Test Scores (Awards / Scantron):** `[DEFERRED — WAITING ON BOBBY]`
    - *Mr. Muth's email:* "Convention Hosts will schedule more time with Mr. Muth to talk about the awards process (we will use the existing Scantron system unless Mr. Muth approves modifications in the future). Maybe a January check-in?"
    - *Convention Book (Page 4, Sponsors May Do During):* "Input scores/judge for certain events (if applicable; most events will remain on paper)" and "View student test scores (most likely a few days after convention)."
    - **Status (Carl, Nov 24):** Deferred until Carl talks with **Bobby (Awards Chair)**, the presidents, and Mr. Muth. Questions to resolve in that conversation:
      - Which specific during-convention events (if any) will have online score entry by sponsors/judges (including Olympika scoring uploads)?
      - How will Scantron / event scores be uploaded (e.g., Google Sheet template upload) and who can view them post-convention (sponsors only vs. delegates for their own scores)?
      - What format is needed for converting scores into an awards slideshow?
      - Confirm: per Mr. Muth's email ("no public awards lists with student names"), test scores and placements will **only** be visible to authenticated users — never on any public page.

---

## 6. Backups, Logistics, Venue & Minor Details

39. **Reliable Google Sheet Backup Sync:**
    - *Mr. Muth's email:* "The most important info we need to run convention should be backed up somewhere more reliable in case a new tool has an outage or breaks (e.g., all registration data and schedule exported/synced to a Google sheet)."
    - **Question:**
      - How often should the automated sync to Google Sheets run (e.g., nightly during registration, every 15–30 minutes during convention weekend, plus a manual "Sync now" button)?
      - Which Google account will own the backup Sheet, and exactly who gets access (Host School Sponsors + Convention Presidents + Registration Chairs)?

40. **Venue Clarification (University High School vs. Woodbridge High School):**
    - *Convention Book (Page 2 & 5):* Says State Convention (March 12–13) is at **University High School, 4771 Campus Drive, Irvine, CA 92612** (co-presented by University and Woodbridge), while **CARCER South (Feb 21)** is at **Woodbridge High School**.
    - *Existing legal docs (`PRIVACY_POLICY.md`, `TERMS_OF_SERVICE.md`):* Previously said the Convention is held at both campuses.
    - **Question:** Are all March 12–13 convention events physically at University High School only (with Woodbridge co-hosting + hosting CARCER South), or are any March 12–13 events held on Woodbridge's campus?

41. **Host School Sponsor Contact Phone Number:**
    - *Convention Book (Page 2):* Lists Mark Michalak as `(714) 514-8815` (`MarkMichalak@iusd.org`) and John Conant as `(714) 360-8923` (`JohnConant@iusd.org`).
    - *Previous `PRIVACY_POLICY.md` / `TERMS_OF_SERVICE.md`:* Listed `(949) 936-7661` (University High School main office?).
    - **Question:** Should legal/privacy notices list Mark Michalak's `(714) 514-8815`, the UHS main office `(949) 936-7661`, or email-only (`state@uhsjcl.org` / `MarkMichalak@iusd.org`)?

42. **Pre-Loading the Convention Book Schedule:**
    - *Convention Book (Pages 8–10):* Contains the full Friday March 12 and Saturday March 13 schedule.
    - **Question:** Should we seed/import the Convention Book's schedule into `schedule_items` now (as published or draft), or wait for the Logistics Chair (Brian Jing) to enter/confirm locations first?

43. **Board Roster & Role Assignments (`board.json`):** `[PARTIALLY RESOLVED]`
    - *Convention Book (Page 11, Dramātis Persōnae):* Lists all 2027 Convention Board officers (Chenyue Zhou & Sriya Kushwaha, Mark Michalak & John Conant, Activities/Academic/Registration/Creative/Athletics/Technology/Certamen/Logistics/Hospitality/Woodbridge Operations Chairs) and CAJCL Executive Committee/Board.
    - **Partial Decision (Carl, Nov 24):** **Brian (Logistics Chair)** needs **full access to everything** in the system. **Registration Chairs** own registration; **Bobby** owns awards; **Mr. Muth & Presidents** get an overall view.
    - **Remaining Question:** Which exact remaining officers from Page 11 should receive which platform roles (`admin`, `registration_chair`, `academics_chair`, `activities_chair`, `athletics_director`, `logistics_chair`, `awards_chair`), and do we need any new scopes (e.g., `certamen` or `hospitality`)?

44. **"COMING SOON!" & `[TBA]` Links in the Convention Book (Page 2 & 6–7):**
    - Board Application deadline `[TBA]`, Scholarship Applications, CAJCL Waiver, Hotel Information, Dramatic Interpretation, STEM Challenge, Convention Website link.
    - **Question:** Which of these will live as Google Doc text pages on our site (`#/site-pages`) vs. static PDFs (uploaded via the Drive → rebuild `/assets/<filename>` pipeline) vs. external links on `cajcl.org`?

45. **Post-Convention PII Retention & Purge Scope (`Blocker: Registration Chairs`):**
    - We are building an admin UI to preview, trigger, and verify PII deletion after convention (April 12, 2027).
    - **Question:** Confirm with Registration Chairs the exact list of fields/records to **keep** in the historical archive vs. **delete** across Turso, Google Drive, and backup Google Sheets.
