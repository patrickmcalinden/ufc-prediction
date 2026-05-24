import type { MDXComponents } from "mdx/types";

// Default MDX renderers. Tailwind utility classes give us readable
// prose without pulling in @tailwindcss/typography. We can swap in
// the typography plugin later in Phase 5 if we want richer styling.
const components: MDXComponents = {
  h1: ({ children }) => (
    <h1 className="text-3xl font-semibold tracking-tight mt-8 mb-4">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-2xl font-semibold tracking-tight mt-8 mb-3">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-xl font-semibold mt-6 mb-2">{children}</h3>
  ),
  p: ({ children }) => <p className="my-4 leading-7">{children}</p>,
  ul: ({ children }) => <ul className="my-4 ml-6 list-disc space-y-1">{children}</ul>,
  ol: ({ children }) => <ol className="my-4 ml-6 list-decimal space-y-1">{children}</ol>,
  a: ({ href, children }) => (
    <a href={href} className="text-blue-600 hover:underline dark:text-blue-400">
      {children}
    </a>
  ),
  code: ({ children }) => (
    <code className="rounded bg-neutral-100 px-1 py-0.5 text-sm font-mono dark:bg-neutral-800">
      {children}
    </code>
  ),
  pre: ({ children }) => (
    <pre className="my-4 overflow-x-auto rounded-lg bg-neutral-900 p-4 text-sm text-neutral-100">
      {children}
    </pre>
  ),
};

export function useMDXComponents(): MDXComponents {
  return components;
}
