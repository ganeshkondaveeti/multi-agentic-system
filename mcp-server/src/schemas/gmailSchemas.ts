import { z } from 'zod';

// `to` may be empty: Reply Desk never stores the customer's address, so the person who
// sends the draft from Gmail adds it there.
export const GmailDraftInputSchema = z.object({
  to: z.array(z.string().email("Invalid email address")).optional().default([]),
  cc: z.array(z.string().email("Invalid email address")).optional().default([]),
  bcc: z.array(z.string().email("Invalid email address")).optional().default([]),
  subject: z.string().min(1, "Subject cannot be empty"),
  body: z.string().min(1, "Body cannot be empty"),
});

export type GmailDraftInput = z.infer<typeof GmailDraftInputSchema>;
