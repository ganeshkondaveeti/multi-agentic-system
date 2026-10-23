// Which agents a pushback will re-run. A preview of `session.classify_pushback` on the
// server, using the same cue patterns. The server decides; this only labels the button.

const FOF = String.raw`(?:\s+etf)?(?:\s+(?:fund\s+of\s+funds?|fof))?`;
const TAIL = String.raw`(?:\s+fund)?(?:\s+direct(?:\s+plan)?)?(?:\s+growth)?`;

const SCHEME_MENTION = new RegExp(
  String.raw`(?:\bhdfc\s+)?(?:\bgold${FOF}${TAIL}|\bsilver${FOF}${TAIL}|\blarge[\s-]?cap${TAIL}` +
    String.raw`|\bmid[\s-]?cap${TAIL}|\bsmall[\s-]?cap${TAIL})\b`,
  "i",
);
const OTHER_SCHEME =
  /\b(?:different|another|other|wrong|not\s+(?:the|that|this)(?:\s+same)?)\s+(?:scheme|fund|fof|etf)\b/i;
const THEME_WORD = new RegExp(
  String.raw`\bexit[\s-]?loads?\b|\bbrokerage\b|\bfees?\b|\bcharg(?:e|es|ed|ing)\b` +
    String.raw`|\bcommissions?\b|\bexpense\s+ratio\b` +
    String.raw`|\bwithdr(?:aw\w*|ew)\b|\bdeposits?\b|\bpayments?\b|\brefunds?\b|\bupi\b|\bbanks?\b` +
    String.raw`|\bcharts?\b|\borders?\b|\btrades?\b|\bgtt\b|\bbuy\/sell\b` +
    String.raw`|\bcrash(?:es|ed|ing)?\b|\bslow\b|\blags?\b|\bfreez(?:e|es|ing)\b|\bbugs?\b` +
    String.raw`|\blog[\s-]?in\b`,
  "i",
);
const WINDOW_WORD = new RegExp(
  String.raw`\blast\s+(?:week|month|\d+\s+days)\b|\bthis\s+week\b|\brecent(?:ly)?\b` +
    String.raw`|\bpatterns?\b|\bthemes?\b|\btrends?\b|\bspikes?\b|\bsurges?\b|\bwindow\b` +
    String.raw`|\brecurring\b|\brising\b|\bone[\s-]?off\b|\bwidespread\b|\bwider\b` +
    String.raw`|\bother\s+(?:users|customers|people|reviews|complaints)\b|\bhow\s+many\b`,
  "i",
);

export type Rerun = "facts" | "pattern";

export function footprint(pushback: string): Rerun[] {
  const rerun: Rerun[] = [];
  if (SCHEME_MENTION.test(pushback) || OTHER_SCHEME.test(pushback)) rerun.push("facts");
  if (THEME_WORD.test(pushback) || WINDOW_WORD.test(pushback)) rerun.push("pattern");
  return rerun;
}
