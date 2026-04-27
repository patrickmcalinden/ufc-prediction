import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { Link } from 'react-router-dom';

export default function Blog() {
  const { data: posts, isLoading } = useQuery({
    queryKey: ['blog_posts'],
    queryFn: api.getBlogPosts,
  });

  return (
    <div className="flex flex-col gap-6 w-full animate-fade-in-up pb-20 mt-4">
      <div className="flex justify-between items-end mb-4">
        <div>
          <h1 className="text-4xl md:text-5xl font-black tracking-tight mb-2">TWISTER Journal</h1>
          <p className="text-gray-400 font-medium">Algorithmic analysis, betting strategy, and engineering logs.</p>
        </div>
      </div>

      {isLoading ? (
        <div className="text-gray-400 font-bold tracking-widest animate-pulse">FETCHING PUBLICATIONS...</div>
      ) : (
        <div className="flex flex-col gap-6">
          {posts?.length === 0 && <p className="text-white">No posts active in MDX pipeline.</p>}
          {posts?.map(post => (
            <Link key={post.slug} to={`/blog/${post.slug}`} className="glass-panel p-8 md:p-10 rounded-3xl hover:scale-[1.01] transition-transform hover:border-ufcred-500/50 flex justify-between items-center group">
              <div className="flex flex-col gap-1">
                <p className="text-ufcred-500 font-bold tracking-widest uppercase text-xs mb-2">{post.published_at || 'Recently Published'}</p>
                <h2 className="text-3xl lg:text-4xl font-black tracking-tight text-white group-hover:text-ufcred-500 transition-colors uppercase leading-none">{post.title}</h2>
                <p className="text-gray-400 font-medium mt-3 text-lg">{post.summary || "Click to triangulate full log mappings and engineering notes."}</p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
