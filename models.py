from dataclasses import dataclass

@dataclass
class RedditPost:
    author: str
    published_at: str
    title: str
    post_url: str
    votes: str
    comments_count: str
    media_url: str