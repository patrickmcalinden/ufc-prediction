"use client";

export default function ModelTabs({
  models,
  active,
  onChange,
}: {
  models: string[];
  active: string;
  onChange: (m: string) => void;
}) {
  if (models.length <= 1) return null;
  return (
    <div className="mb-4 inline-flex rounded-lg border border-neutral-200 p-1 text-sm dark:border-neutral-800">
      {models.map((m) => (
        <button
          key={m}
          type="button"
          onClick={() => onChange(m)}
          className={`rounded-md px-3 py-1 font-mono transition-colors ${
            m === active
              ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
              : "text-neutral-500 hover:text-foreground"
          }`}
        >
          {m}
        </button>
      ))}
    </div>
  );
}
