import openpyxl
import re
from typing import List
from models import RedditPost


class ExcelService:
    def save(self, filename: str, posts: List[RedditPost]):
        safe_name = re.sub(r'[\\/*?:"<>|]', "", filename).strip()
        full_path = f"{safe_name}.xlsx"

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Posts"

        ws.append(["Автор", "Дата", "Заголовок", "Ссылка", "Лайки", "Комменты", "Медиа"])

        for post in posts:
            ws.append([
                post.author,
                post.published_at,
                post.title,
                post.post_url,
                post.votes,
                post.comments_count,
                post.media_url
            ])

        wb.save(full_path)
        return full_path