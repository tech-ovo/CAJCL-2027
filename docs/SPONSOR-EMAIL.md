# The email to sponsors

The one message that opens registration. It goes to every chapter's Latin
teacher or sponsor, and for most of them it will be the only thing they read
before they start.

**Every fact in it comes from Settings.** Before sending, open
**Settings → Values** and read the fee, the deadlines and the dates off the
page rather than out of last year's email.

---

## What it has to do

Four things, and nothing else:

1. Tell them **what to do first** — sign in, paste a roster. One action.
2. Tell them **what it costs** and **when the money is due**.
3. Tell them **which forms are paper**, because that is the part no software
   can do for them.
4. Tell them **who to ask** when it goes wrong.

Anything beyond that is competing with the four things that matter. A sponsor
reading this is between classes.

---

## Draft

> **Subject:** Registration is open — 72nd CAJCL State Convention, March 12–13

Dear Latin teachers and JCL sponsors,

Registration for the **72nd California Junior Classical League State
Convention** is now open. The convention is **March 12–13, 2027**, hosted
jointly by University High School and Woodbridge High School, with everything
taking place on the University High School campus at 4771 Campus Drive, Irvine.

Registration is online this year, at **state.uhsjcl.org**. Your access code is
at the bottom of this email.

**What to do first**

Sign in and paste your roster. You do not need to format it — paste a column
out of a spreadsheet, a numbered list, or one name per line, and it will read
it. You will see exactly what it understood before anything is saved, and you
can correct any row. Most chapters finish this in under five minutes.

Each of your delegates and adults then gets a sheet with their own access code
and a square code they can scan with a phone camera. Hand each sheet to the
person named on it. They sign in and complete their own form: grade, Latin
level, meal preference, and the events they would like to enter.

**None of the event choices are binding.** They tell the Academics, Activities
and Athletics chairs how many students to prepare materials for, and your
delegates can change their answers as often as they like until the deadline.

**What it costs**

| | |
| --- | --- |
| Per delegate | $140.00 |
| Adults | one free per 10 delegates |
| Each additional adult | $75.00 |

Your invoice is on the site and updates itself as your roster changes, so check
it there rather than working from a printed copy. Make checks payable to
**University High School JCL c/o Mark Michalak**, and write your chapter name on
the memo line so we can match the payment to your invoice.

**Dates to keep**

| | |
| --- | --- |
| Forms close | February 13, 2027 |
| Payment due | February 13, 2027 |
| Convention | March 12–13, 2027 |

After the forms deadline your delegates can no longer edit their own answers.
You can still ask a registration chair to reopen a form.

**Three forms are on paper and are not online**

- **Student Waiver** — every delegate, parent or guardian signature required
- **Student Medical Form** — every delegate, parent or guardian signature required
- **Adult Medical Form** — every adult attending, sponsors included

Collect all three, tick each one off in your roster on the site as it reaches
you, scan the packet into your chapter's Drive folder, and mail the paper with
your check. Signatures and legibility are checked at Friday check-in.

**If something goes wrong**

Reply to this email, or write to **state@uhsjcl.org**. If a delegate loses
their sheet you can issue them a new code yourself from your roster — the old
one stops working immediately.

We are looking forward to seeing your chapter in March.

*[Name]*
*Registration Chair, 72nd CAJCL State Convention*
*state@uhsjcl.org*

---

**Your chapter:** [Chapter name]
**Your access code:** `SPO-XXXXX-XXXXX`

Keep this code. Anyone who has it can sign in as you and see your whole
chapter. If you lose it, write to state@uhsjcl.org and we will issue another.

---

## Before you send it

- [ ] The fee, the deadlines and the dates match **Settings → Values**.
      Check the *additional adult* fee especially: it is the one figure in this
      email that is not on any other page, and the first draft of this document
      had it wrong
- [ ] The remit-to name matches `invoice.remit_to`
- [ ] Every sponsor is on the site with a code — codes are shown **once**, so
      generate the list and send it the same day
- [ ] The site is deployed and answers at the address in the email
- [ ] Somebody who is not you has read it and can say what to do first

## Sending it

Send **one message per chapter**, not one message to everybody. Each sponsor's
access code is a credential and belongs only to them; a code in a message with
forty recipients is a code forty people hold.

The mail merge wants two columns — chapter name and access code — and
`board-codes.txt` is where the codes come from after you run
`modal run backend/app.py::board`. **Delete that file once the emails are
sent.** It is the only place the codes exist in the clear, and it is gitignored
so it will not be committed by accident.

## Two weeks later

Chapters that have not started are the ones to chase, and the Chapters page
tells you which they are at a glance: no delegates, nothing paid. That is a
short second email, not a repeat of this one.
