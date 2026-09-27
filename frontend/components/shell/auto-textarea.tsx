"use client";

import { useLayoutEffect, useRef, type TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

/**
 * A textarea that grows with its content instead of scrolling inside a fixed
 * box. `minRows` sets the resting height; past that the field follows the text,
 * so an edited analysis is readable in full without a scrollbar.
 */
export function AutoTextarea({
  className,
  minRows = 2,
  value,
  onChange,
  ...props
}: Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "rows"> & {
  minRows?: number;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  // Collapse first so the field can shrink again when lines are deleted.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  return (
    <textarea
      ref={ref}
      rows={minRows}
      value={value}
      onChange={onChange}
      className={cn("resize-none overflow-hidden", className)}
      {...props}
    />
  );
}
