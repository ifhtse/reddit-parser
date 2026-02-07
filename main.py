import asyncio
import random
from datetime import datetime
from playwright.async_api import async_playwright

from models import RedditPost
from logger_config import setup_logger
from excel_service import ExcelService


class RedditScraper:
    def __init__(self):
        self.logger = setup_logger()
        self.excel = ExcelService()
        self.url = "https://www.reddit.com"

    async def run(self):
        try:
            limit_input = input("Enter posts limit (default 3): ").strip()
            limit = int(limit_input) if limit_input.isdigit() else 3
        except:
            limit = 3

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"]
            )

            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                locale='en-US',
                timezone_id='America/New_York'
            )

            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            page = await context.new_page()

            try:
                self.logger.info("1. Navigating to Reddit...")
                await page.goto(self.url)

                self.logger.info("Waiting 15s for manual check...")
                await page.wait_for_timeout(15000)

                try:
                    await page.get_by_role("button", name="Decline all").click(timeout=2000)
                    await page.locator("button:has-text('Close')").click(timeout=2000)
                except:
                    pass

                self.logger.info("2. Locating search field...")

                menu_open = False
                if await page.locator("faceplate-tracker a").count() > 0:
                    menu_open = True

                if not menu_open:
                    search = page.locator("input[name='q']").first
                    if await search.count() == 0:
                        search = page.get_by_role("searchbox").first

                    if await search.count() > 0:
                        await search.evaluate("element => element.click()")
                        await search.evaluate("element => element.focus()")
                    else:
                        await page.keyboard.press("/")

                self.logger.info("3. Selecting trend...")
                await page.wait_for_timeout(3000)

                trending_items = await page.locator("faceplate-tracker a").all()
                if not trending_items:
                    trending_items = await page.locator("#search-dropdown-element a").all()

                query_text = "Python"

                if trending_items:
                    random_item = random.choice(trending_items[:5])
                    text = await random_item.inner_text()
                    query_text = text.split('\n')[0].strip()
                    self.logger.info(f"Selected trend: {query_text}")
                    await random_item.click()
                else:
                    self.logger.warning("Trends not found. Using fallback query.")
                    if await page.locator("input[name='q']").count() > 0:
                        await page.locator("input[name='q']").fill("Python")
                        await page.keyboard.press("Enter")

                self.logger.info("4. Extracting posts data...")
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_timeout(5000)

                articles = await page.locator("shreddit-post").all()
                if not articles:
                    articles = await page.locator("article").all()
                if not articles:
                    articles = await page.locator("[data-testid='post-container']").all()

                self.logger.info(f"Found {len(articles)} posts. Parsing top {limit}...")

                posts_data = []

                for i, article in enumerate(articles[:limit]):
                    try:
                        title = await article.get_attribute("post-title")
                        if not title:
                            t_el = article.locator("h1, h2, h3, h4, div[id*='post-title']").first
                            if await t_el.count() > 0:
                                title = await t_el.inner_text()
                        title = title or "No Title"

                        post_url = await article.get_attribute("permalink")
                        if not post_url:
                            url_el = article.locator("a[href*='/comments/']").first
                            if await url_el.count() > 0:
                                post_url = await url_el.get_attribute("href")

                        if post_url and not post_url.startswith("http"):
                            post_url = f"https://www.reddit.com{post_url}"
                        post_url = post_url or "None"

                        author = await article.get_attribute("author")
                        if not author:
                            a_el = article.locator("a[href*='/user/']").first
                            if await a_el.count() > 0:
                                author = await a_el.inner_text()
                        author = author or "Unknown"

                        ts = await article.get_attribute("created-timestamp")
                        if not ts:
                            time_el = article.locator("time").first
                            if await time_el.count() > 0:
                                ts = await time_el.get_attribute("datetime")

                        if ts:
                            try:
                                clean_ts = ts.replace('Z', '+00:00').split('.')[0]
                                dt = datetime.fromisoformat(clean_ts)
                                date_str = dt.strftime("%d.%m.%Y %H:%M")
                            except:
                                date_str = datetime.now().strftime("%d.%m.%Y %H:%M")
                        else:
                            date_str = datetime.now().strftime("%d.%m.%Y %H:%M")

                        votes = await article.get_attribute("score")
                        if not votes:
                            v_el = article.locator("[id*='vote-count']").first
                            votes = await v_el.inner_text() if await v_el.count() > 0 else "0"

                        comments = await article.get_attribute("comment-count")
                        if not comments:
                            c_el = article.locator("[data-test-id='comment-count']").first
                            comments = await c_el.inner_text() if await c_el.count() > 0 else "0"

                        media = "None"
                        imgs = article.locator("img").all()
                        for img in await imgs:
                            src = await img.get_attribute("src")
                            if src and ("external-preview" in src or "i.redd.it" in src):
                                media = src
                                break

                        posts_data.append(RedditPost(author, date_str, title, post_url, votes, comments, media))
                        self.logger.info(f"Parsed item {i + 1}: {title[:30]}...")

                    except Exception as e:
                        self.logger.error(f"Error parsing item {i}: {e}")

                if posts_data:
                    if not query_text or not query_text.strip():
                        query_text = "Reddit_Result"

                    file_name = self.excel.save(query_text, posts_data)
                    self.logger.info(f"Success. File saved: {file_name}")
                else:
                    self.logger.warning("No data collected.")

            except Exception as e:
                self.logger.error(f"Critical error: {e}", exc_info=True)
                await page.screenshot(path="fatal_error.png")
            finally:
                await browser.close()


if __name__ == "__main__":
    bot = RedditScraper()
    asyncio.run(bot.run())