import Link from "next/link";
import { listPosts } from "@/lib/blog";

export const metadata = { title: "Blog · UFC Predictor" };

export default async function BlogIndex() {
  const posts = await listPosts();
  return (
    <div>
      <h1 className="text-3xl font-semibold tracking-tight">Blog</h1>
      <ul className="mt-6 divide-y divide-neutral-200 dark:divide-neutral-800">
        {posts.length === 0 && (
          <li className="py-8 text-neutral-500">No posts yet.</li>
        )}
        {posts.map((p) => (
          <li key={p.slug} className="py-5">
            <Link href={`/blog/${p.slug}/`} className="group block">
              <p className="text-xs tabular-nums text-neutral-500">{p.date}</p>
              <h2 className="mt-1 text-lg font-medium group-hover:underline">{p.title}</h2>
              {p.summary && (
                <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">{p.summary}</p>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
