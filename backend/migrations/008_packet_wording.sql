-- One sheet of instructions was written for a delegate, and everybody got it.
--
-- A sponsor holding their own access sheet was told to complete the Student
-- Activity Sheet, which does not exist for them, and to ask their sponsor for
-- a new code, which is themselves. A chaperone was told to enter events.
--
-- Three documents now, chosen by who is holding the sheet. See
-- backend/lib/printing.py::_packet_sheet. The delegate wording keeps the
-- original key so nothing that already refers to it has to change.

INSERT INTO documents (key, title, body_md, updated_at) VALUES
  ('packet_instructions_adult', 'Packet instructions for adults',
   'Your access code is printed above. Scan the square code with your phone camera, or type the code into **state.uhsjcl.org**.

**Keep this sheet.** Anyone holding it can sign in as you. If you lose it, ask your chapter''s sponsor for a new code — the old one stops working immediately.

Once you are signed in, complete your **Adult Registration Form**. It asks for your contact details, your meal preference, how much Latin you know, and which jobs you are willing to help with over the weekend. Nothing there commits you to a role; it tells the chairs who they can ask.

One form is **not** online and must be signed on paper: the **Adult Medical Form**. Sign it by hand and give it to your chapter''s sponsor.',
   strftime('%Y-%m-%dT%H:%M:%SZ','now')),

  ('packet_instructions_sponsor', 'Packet instructions for sponsors',
   'Your access code is printed above. Scan the square code with your phone camera, or type the code into **state.uhsjcl.org**.

**Keep this sheet.** Anyone holding it can sign in as you, and your account can see and change your whole chapter. If you lose it, ask a convention chair for a new code — the old one stops working immediately.

Signing in gives you your chapter''s roster, your invoice, and this packet. To finish your chapter''s registration:

1. Give every attendee the sheet with their name on it.
2. Complete your own **Adult Registration Form**, the same as any other adult.
3. Collect the signed waivers and medical forms, and tick each one off in your roster as it arrives.
4. Scan the paper into your chapter''s Drive folder.
5. Mail the paper and your chapter''s check to the address on the invoice.

The **Adult Medical Form** applies to you as well as to your chaperones.',
   strftime('%Y-%m-%dT%H:%M:%SZ','now'))
ON CONFLICT (key) DO NOTHING;
