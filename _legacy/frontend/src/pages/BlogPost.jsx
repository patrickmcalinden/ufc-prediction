import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { useParams, Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';

export default function BlogPost() {
  const { slug } = useParams();
  const { data: post, isLoading, error } = useQuery({
    queryKey: ['blog_post', slug],
    queryFn: () => api.getBlogPost(slug),
  });

  if (isLoading) return <div className="text-gray-400 font-bold tracking-widest animate-pulse text-center mt-12 pb-20">PARSING MDX LOGIC...</div>;
  if (error || !post) return <div className="text-red-500 text-center font-bold mt-12 pb-20">Failed to locate publication route.</div>;

  return (
    <div className="flex flex-col gap-8 w-full max-w-4xl mx-auto animate-fade-in-up pb-32 mt-4">
      <Link to="/blog" className="text-gray-400 hover:text-white text-sm font-bold tracking-widest uppercase inline-flex items-center gap-2 transition-colors">
        &larr; Back to Journal
      </Link>
      
      <div className="glass-panel p-8 md:p-16 rounded-[2rem] border-t-ufcred-500 border-t-4 bg-ufcslate-900/40">
        <p className="text-ufcred-500 font-black tracking-widest uppercase text-sm mb-4">{post.metadata?.date || 'Undated'}</p>
        <h1 className="text-5xl md:text-7xl font-black tracking-tighter uppercase leading-none mb-12">
          {post.metadata?.title || post.slug}
        </h1>
        
        <div className="prose prose-invert prose-red max-w-none prose-h1:font-black prose-h2:font-black prose-h3:font-black prose-a:text-ufcred-500 hover:prose-a:text-ufcred-400 prose-img:rounded-3xl prose-p:font-medium prose-p:text-gray-300">
          <ReactMarkdown>{post.content}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
