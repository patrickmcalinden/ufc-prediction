"use client";

import Link from "next/link";
import { useState } from "react";

const links = [
  { href: "/", label: "Predictions" },
  { href: "/performance", label: "Performance" },
  { href: "/methodology", label: "Methodology" },
  { href: "/blog", label: "Blog" },
];

export default function Nav() {
  const [open, setOpen] = useState(false);

  return (
    <header className="border-b border-neutral-200 dark:border-neutral-800">
      <nav className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-4">
        <Link
          href="/"
          className="font-semibold tracking-tight"
          onClick={() => setOpen(false)}
        >
          UFC Predictor
        </Link>

        <ul className="hidden gap-5 text-sm text-neutral-600 sm:flex dark:text-neutral-300">
          {links.map((l) => (
            <li key={l.href}>
              <Link href={l.href} className="hover:text-foreground transition-colors">
                {l.label}
              </Link>
            </li>
          ))}
        </ul>

        <button
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="-mr-2 inline-flex h-10 w-10 items-center justify-center rounded-md text-neutral-700 sm:hidden dark:text-neutral-200"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-5 w-5"
          >
            {open ? (
              <>
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </>
            ) : (
              <>
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </>
            )}
          </svg>
        </button>
      </nav>

      {open && (
        <ul className="border-t border-neutral-200 px-4 py-2 text-sm text-neutral-700 sm:hidden dark:border-neutral-800 dark:text-neutral-200">
          {links.map((l) => (
            <li key={l.href}>
              <Link
                href={l.href}
                onClick={() => setOpen(false)}
                className="block py-2"
              >
                {l.label}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </header>
  );
}
