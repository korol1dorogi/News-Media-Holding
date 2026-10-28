import type { Post } from "../types";
import { formatTime } from "./labels";

interface Props {
  posts: Post[];
  highlightId: string | null;
  firstSourceId: string;
}

export default function PostList({ posts, highlightId, firstSourceId }: Props) {
  if (posts.length === 0) {
    return <p className="text-sm text-slate-500">Посты-источники для этого события не загружены.</p>;
  }
  return (
    <ul className="space-y-2">
      {posts.map((post) => (
        <li
          key={post.id}
          id={`post-${post.id}`}
          className={`rounded-lg border bg-white p-3 text-sm transition ${
            post.id === highlightId ? "border-blue-500 ring-2 ring-blue-200" : "border-slate-200"
          }`}
        >
          <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span className="font-mono">{post.id}</span>
            <span>{post.channel_id}</span>
            <span>{formatTime(post.ts)}</span>
            {post.id === firstSourceId && (
              <span className="rounded bg-amber-100 px-1.5 text-amber-900">первоисточник</span>
            )}
            {post.forward_from && <span>пересылка {post.forward_from}</span>}
            {post.media.length > 0 && <span>фото: {post.media.join(", ")}</span>}
          </div>
          <p className="whitespace-pre-line">{post.text}</p>
        </li>
      ))}
    </ul>
  );
}
