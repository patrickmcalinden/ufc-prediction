import Link from "next/link";

const links = [
  { href: "/", label: "Predictions" },
  { href: "/performance", label: "Performance" },
  { href: "/methodology", label: "Methodology" },
  { href: "/blog", label: "Blog" },
];

export default function Nav() {
  return (
    <header className="border-b border-neutral-200 dark:border-neutral-800">
      <nav className="mx-auto flex max-w-5xl items-center justify-between gap-6 px-4 py-4">
        <Link href="/" className="font-semibold tracking-tight">
          UFC Predictor
        </Link>
        <ul className="flex gap-5 text-sm text-neutral-600 dark:text-neutral-300">
          {links.map((l) => (
            <li key={l.href}>
              <Link href={l.href} className="hover:text-foreground transition-colors">
                {l.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  );
}
