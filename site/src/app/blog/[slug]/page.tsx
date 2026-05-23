import { notFound } from "next/navigation";
import { getPostBySlug, listSlugs } from "@/lib/blog";

export async function generateStaticParams() {
  const slugs = await listSlugs();
  return slugs.map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = await getPostBySlug(slug);
  return { title: post ? `${post.title} · UFC Predictor` : "Post · UFC Predictor" };
}

export default async function PostPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = await getPostBySlug(slug);
  if (!post) notFound();

  return (
    <article>
      <header className="mb-6">
        <p className="text-sm tabular-nums text-neutral-500">{post.date}</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">{post.title}</h1>
      </header>
      <div className="prose-content" dangerouslySetInnerHTML={{ __html: post.html }} />
    </article>
  );
}
