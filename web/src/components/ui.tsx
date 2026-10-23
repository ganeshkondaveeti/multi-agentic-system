import type { ButtonHTMLAttributes, ReactNode } from "react";

// Small shared pieces in the Stitch visual language: matte surfaces, 1px lines,
// mono labels, and pills. Icons are inline SVG (no icon font, no CDN).

const ICONS = {
  plus: "M12 5v14M5 12h14",
  shield: "M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z",
  lock: "M7 11V8a5 5 0 0110 0v3M6 11h12v9H6z",
  check: "M5 12.5l4.5 4.5L19 7.5",
  x: "M6 6l12 12M18 6L6 18",
  alert: "M12 4l9 16H3l9-16zM12 10v4M12 17.5v.5",
  history: "M4 12a8 8 0 103-6.2M4 4v4h4M12 8v4l3 2",
  link: "M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1M14 10a4 4 0 00-5.7 0l-3 3a4 4 0 005.7 5.7l1-1",
  search: "M11 18a7 7 0 100-14 7 7 0 000 14zM20 20l-4-4",
  play: "M8 5v14l11-7z",
  download: "M12 4v11M7 10l5 5 5-5M5 20h14",
  layers: "M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5",
  facts: "M4 5h16v14H4zM4 10h16M9 10v9",
  pattern: "M4 18l5-6 4 3 7-9M15 6h5v5",
  doc: "M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6",
  timeline: "M4 6h7M4 12h12M4 18h9",
  refresh: "M20 11a8 8 0 10-2.3 5.7M20 4v7h-7",
  inbox: "M4 13l2-8h12l2 8M4 13v6h16v-6M4 13h5l1 2h4l1-2h5",
  chevron: "M9 6l6 6-6 6",
  close: "M6 6l12 12M18 6L6 18",
  bolt: "M13 3L5 13h6l-1 8 8-10h-6z",
  route: "M6 19a2 2 0 100-4 2 2 0 000 4zM18 9a2 2 0 100-4 2 2 0 000 4zM6 15V9a3 3 0 013-3h7M18 9v6a3 3 0 01-3 3H8",
} as const;

export type IconName = keyof typeof ICONS;

export function Icon({ name, className = "h-4 w-4" }: { name: IconName; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d={ICONS[name]} />
    </svg>
  );
}

export function Badge({
  className = "bg-raised text-muted border-line",
  children,
  testId,
  title,
}: {
  className?: string;
  children: ReactNode;
  testId?: string;
  title?: string;
}) {
  return (
    <span
      data-testid={testId}
      title={title}
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded border px-1.5 py-0.5 font-mono text-[11px] font-semibold leading-4 ${className}`}
    >
      {children}
    </span>
  );
}

export function Label({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <span className={`font-mono text-trace-mono uppercase tracking-wider text-muted ${className}`}>
      {children}
    </span>
  );
}

export function Card({
  title,
  icon,
  right,
  children,
  className = "",
  testId,
  accent,
}: {
  title?: ReactNode;
  icon?: IconName;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  testId?: string;
  accent?: string;
}) {
  return (
    <section
      data-testid={testId}
      className={`rounded-lg border border-line bg-panel ${accent ?? ""} ${className}`}
    >
      {title !== undefined && (
        <header className="flex items-center justify-between gap-2 border-b border-line px-3 py-2">
          <h2 className="flex items-center gap-2 text-headline-sm text-ink">
            {icon && <Icon name={icon} className="h-4 w-4 text-muted" />}
            {title}
          </h2>
          {right}
        </header>
      )}
      <div className="p-3">{children}</div>
    </section>
  );
}

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-primary-container text-canvas font-semibold hover:bg-primary disabled:bg-raised disabled:text-muted",
  secondary:
    "border border-line text-ink hover:bg-raised hover:border-outline disabled:text-muted disabled:hover:bg-transparent",
  ghost: "text-muted hover:text-ink hover:bg-raised disabled:text-outline",
  danger: "text-danger hover:bg-danger/10 border border-transparent hover:border-danger",
};

export function Button({
  variant = "secondary",
  className = "",
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return (
    <button
      type="button"
      {...props}
      className={`inline-flex h-8 items-center justify-center gap-1.5 rounded px-3 text-body-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary-container disabled:cursor-not-allowed ${VARIANTS[variant]} ${className}`}
    >
      {children}
    </button>
  );
}

export function Spinner({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={`animate-spin ${className}`} aria-hidden="true">
      <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 00-9-9" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function ErrorNote({ message, testId }: { message: string; testId?: string }) {
  return (
    <div
      role="alert"
      data-testid={testId}
      className="flex items-start gap-2 rounded border border-danger/40 bg-danger/10 px-3 py-2 text-body-sm text-danger"
    >
      <Icon name="alert" className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
}
