import { useId, useState, type ReactNode } from "react";

type GoogleReviewInfoButtonProps = {
  title: string;
  children: ReactNode;
  className?: string;
};

/** Fekete körben fehér „i” — kattintásra magyarázó felugró. */
export default function GoogleReviewInfoButton({ title, children, className }: GoogleReviewInfoButtonProps) {
  const [open, setOpen] = useState(false);
  const titleId = useId();

  return (
    <>
      <button
        type="button"
        className={
          className ??
          "inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-black text-[10px] font-bold leading-none text-white"
        }
        aria-label={title}
        onClick={() => setOpen(true)}
      >
        i
      </button>
      {open ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          onClick={() => setOpen(false)}
        >
          <div
            className="relative w-full max-w-md rounded-lg border border-[var(--color-border)] bg-[var(--color-card)] p-5 shadow-lg"
            onClick={(event) => event.stopPropagation()}
          >
            <h2 id={titleId} className="mb-3 text-base font-semibold text-[var(--color-foreground)]">
              {title}
            </h2>
            <div className="space-y-3 text-sm leading-relaxed text-[var(--color-muted-foreground)]">{children}</div>
            <div className="mt-5 flex justify-end">
              <button
                type="button"
                className="rounded border border-[var(--color-border)] px-4 py-2 text-sm text-[var(--color-foreground)]"
                onClick={() => setOpen(false)}
              >
                OK
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
