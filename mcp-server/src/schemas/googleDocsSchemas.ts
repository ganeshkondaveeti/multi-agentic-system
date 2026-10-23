import { z } from 'zod';

export const GoogleDocsAppendSchema = z.object({
  document_id: z.string().min(1, "Document ID cannot be empty"),
  content: z.string().min(1, "Content cannot be empty"),
});

export type GoogleDocsAppendInput = z.infer<typeof GoogleDocsAppendSchema>;
