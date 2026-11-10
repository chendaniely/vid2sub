import { type ReactNode, useEffect, useId, useRef } from "react";

import { cn } from "@/lib/utils";

/** A modal dialog, or with `side` a sheet at that edge, on the native <dialog> element.
 * showModal() puts it in the top layer, makes the rest of the page inert for focus and screen
 * readers, closes it on Esc and moves focus in and, on close, back to the opener. Radix's modal
 * parts inject a <style> element, which the CSP blocks (Task 12's probe), so the editor's modal
 * parts are this one. Scroll lock is the `dialog-open` class on <html>, from index.css: a class,
 * which the CSP allows, where an inline style isn't. */
export function Dialog({ open, onClose, title, side, children, className }: {
  open: boolean;
  onClose: () => void;
  title: string;
  side?: "left" | "right";
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
      document.documentElement.classList.add("dialog-open");
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);
  useEffect(() => () => document.documentElement.classList.remove("dialog-open"), []);
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      data-side={side}
      onClose={() => {
        document.documentElement.classList.remove("dialog-open");
        onClose();
      }}
      className={cn(
        "rounded-lg border border-border bg-popover p-4 text-popover-foreground shadow-lg backdrop:bg-black/40",
        side && "m-0 h-dvh max-h-none w-96 max-w-full rounded-none data-[side=left]:mr-auto data-[side=right]:ml-auto",
        className,
      )}
    >
      <h2 id={titleId} className="mb-3 font-bold">{title}</h2>
      {children}
    </dialog>
  );
}
