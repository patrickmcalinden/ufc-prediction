// Blog post loader. Posts live as .md files in the repo's /blog directory
// (one level above /site). We parse YAML frontmatter with gray-matter and
// render markdown to HTML with marked. Static-export friendly — runs at
// build time only.

import { promises as fs } from "fs";
import path from "path";

import matter from "gray-matter";
import { marked } from "marked";

const BLOG_DIR = path.join(process.cwd(), "..", "blog");

export interface PostMeta {
  slug: string;
  title: string;
  date: string;
  summary: string;
}

export interface Post extends PostMeta {
  html: string;
}

async function readPostFile(filename: string): Promise<Post> {
  const raw = await fs.readFile(path.join(BLOG_DIR, filename), "utf-8");
  const { data, content } = matter(raw);
  const html = await marked.parse(content);
  return {
    slug: String(data.slug ?? filename.replace(/\.md$/, "")),
    title: String(data.title ?? "Untitled"),
    date: String(data.date ?? ""),
    summary: String(data.summary ?? ""),
    html,
  };
}

export async function listPosts(): Promise<PostMeta[]> {
  let files: string[];
  try {
    files = await fs.readdir(BLOG_DIR);
  } catch {
    return [];
  }
  const posts = await Promise.all(
    files.filter((f) => f.endsWith(".md")).map(readPostFile),
  );
  // newest first
  return posts
    .map(({ html: _html, ...meta }) => meta)
    .sort((a, b) => (a.date < b.date ? 1 : -1));
}

export async function getPostBySlug(slug: string): Promise<Post | null> {
  let files: string[];
  try {
    files = await fs.readdir(BLOG_DIR);
  } catch {
    return null;
  }
  for (const f of files) {
    if (!f.endsWith(".md")) continue;
    const post = await readPostFile(f);
    if (post.slug === slug) return post;
  }
  return null;
}

export async function listSlugs(): Promise<string[]> {
  const posts = await listPosts();
  return posts.map((p) => p.slug);
}
