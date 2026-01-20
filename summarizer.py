"""
AI Summarization using multiple models based on URL type
"""
import httpx
import os
import re
import asyncio
from typing import List, Dict
from dataclasses import dataclass
from url_utils import URLType
from logger import get_logger

logger = get_logger(__name__)



@dataclass
class SummaryResult:
    title: str
    summary: str
    key_points: List[str]
    url_type: URLType
    source_url: str
    extra_metadata: dict = None

    def __post_init__(self):
        if self.extra_metadata is None:
            self.extra_metadata = {}


@dataclass
class ResearchResult:
    """For @note tasks without URLs - generates research starter"""
    title: str
    summary: str
    key_points: List[str]
    suggestions: List[str]
    extra_metadata: dict = None

    def __post_init__(self):
        if self.extra_metadata is None:
            self.extra_metadata = {}


# Shared prompt for YouTube video analysis (used by both standalone and X+video flows)
YOUTUBE_ANALYSIS_PROMPT = """Analyze this YouTube video.

CRITICAL: You MUST extract the actual video title and channel name visible on the YouTube page.
Do NOT say "Not mentioned" - these are always visible on YouTube.

Provide:
1. title - The exact video title from YouTube
2. channel - The channel/creator name from YouTube
3. summary - 2-3 sentence overview of the video's message
4. key_points - 5-7 key insights with [MM:SS] or [H:MM:SS] timestamps at the start
5. duration - Video length (e.g., "12:34" or "1:23:45" for longer videos)

If external resources are mentioned, include links: [→](https://url)

JSON format:
{
    "title": "Exact video title from YouTube",
    "channel": "Channel name from YouTube",
    "summary": "...",
    "key_points": ["[02:15] Key point", "[05:30] Another point", "..."],
    "duration": "MM:SS or H:MM:SS"
}"""


class AISummarizer:
    def __init__(self):
        self.xai_key = os.getenv("XAI_API_KEY")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.perplexity_key = os.getenv("PERPLEXITY_API_KEY")
        
        # Folder-aware context prompts
        self.folder_contexts = {
            # Leisure
            "travel": "This is a travel destination. Focus on: best time to visit, must-see attractions, local food/culture, accommodation areas, getting around, and budget tips.",
            "golf courses": "This is a golf course or golf destination. Focus on: course difficulty/rating, signature holes, green fees, best time to play, amenities, and nearby courses.",
            "restaurants and bars": "This is a restaurant or bar. Focus on: cuisine type, signature dishes/drinks, price range, ambiance, reservations, and best times to visit.",
            "shopping": "This is a shopping destination or store. Focus on: what they sell, price range, unique offerings, location, and best deals/times.",
            "biking and hiking": "This is a biking or hiking trail/destination. Focus on: difficulty level, distance, elevation, best seasons, required gear, and trailhead access.",
            
            # Media
            "books": "This is a book. Focus on: author background, genre, main themes, why it's notable, similar books, and who would enjoy it.",
            "movies and shows": "This is a movie or TV show. Focus on: genre, plot summary (no spoilers), director/cast, why it's notable, where to watch, and similar titles.",
            "music": "This is a music artist, album, or song. Focus on: genre, style, notable works, influences, and similar artists.",
            
            # Learning
            "learning": "This is a learning topic. Focus on: core concepts, prerequisites, best resources, practical applications, and learning path.",
            
            # Work/Projects
            "amazing tech": "This is a technology or tool. Focus on: what it does, key features, use cases, pricing, alternatives, and getting started.",
            "automation tasks": "This is an automation idea. Focus on: problem it solves, tools needed, implementation steps, and potential challenges.",
            "portal ideas": "This is a product/portal idea. Focus on: problem statement, target users, key features, competitive landscape, and MVP scope.",
            
            # Health
            "blood and health": "This is a health topic. Focus on: what it is, symptoms/indicators, causes, treatments/management, and when to see a doctor.",
        }
    
    def _get_folder_context(self, project_name: str, parent_project: str = None) -> str:
        """Get context prompt based on folder/project"""
        # Check project name first (more specific)
        key = project_name.lower()
        if key in self.folder_contexts:
            return self.folder_contexts[key]
        
        # Check parent project
        if parent_project:
            parent_key = parent_project.lower()
            if parent_key in self.folder_contexts:
                return self.folder_contexts[parent_key]
        
        # Default generic context
        return "Provide a helpful overview of this topic."
        
    async def summarize(self, url: str, url_type: URLType) -> SummaryResult:
        """Route to appropriate model based on URL type"""
        if url_type == URLType.X_TWITTER:
            return await self._summarize_x_thread(url)
        elif url_type == URLType.YOUTUBE:
            return await self._summarize_youtube(url)
        else:
            return await self._summarize_article(url)
    
    async def _fetch_x_thread_content(self, url: str) -> str:
        """Fetch X/Twitter thread content using Jina Reader"""
        jina_url = f"https://r.jina.ai/{url}"
        logger.debug(f"Fetching X thread content from: {jina_url}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    jina_url,
                    headers={"Accept": "text/markdown"},
                    timeout=30.0,
                    follow_redirects=True
                )
                if response.status_code == 200:
                    content = response.text
                    logger.debug(f"X thread content fetched, length: {len(content)} chars")
                    # Truncate if too long
                    if len(content) > 10000:
                        content = content[:10000] + "\n\n[Content truncated...]"
                    return content
                else:
                    logger.warning(f"Jina non-200 response for X thread: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to fetch X thread content: {e}")

        return ""

    def _extract_youtube_urls(self, content: str) -> List[str]:
        """Extract YouTube URLs from content"""
        youtube_urls = []

        # Full URL patterns (return complete URL)
        full_url_patterns = [
            r'https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'https?://(?:www\.)?youtu\.be/[\w-]+',
            r'https?://m\.youtube\.com/watch\?v=[\w-]+',
        ]

        # Patterns that capture video ID (need to reconstruct URL)
        video_id_patterns = [
            (r'(?<![/\w])youtu\.be/([\w-]+)', 'https://youtu.be/{}'),
            (r'(?<![/\w])youtube\.com/watch\?v=([\w-]+)', 'https://youtube.com/watch?v={}'),
        ]

        # Extract full URLs
        for pattern in full_url_patterns:
            matches = re.findall(pattern, content)
            youtube_urls.extend(matches)

        # Extract video IDs and reconstruct URLs
        for pattern, url_template in video_id_patterns:
            matches = re.findall(pattern, content)
            for video_id in matches:
                youtube_urls.append(url_template.format(video_id))

        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in youtube_urls:
            # Normalize to compare
            normalized = url.replace('www.', '').replace('http://', 'https://')
            if normalized not in seen:
                seen.add(normalized)
                unique_urls.append(url)

        logger.debug(f"Extracted {len(unique_urls)} YouTube URLs from content")
        return unique_urls

    async def _summarize_x_thread(self, url: str) -> SummaryResult:
        """Use Grok to analyze pre-fetched X/Twitter thread content.

        If the thread contains YouTube links, runs parallel Gemini analysis
        and merges results for a comprehensive summary.
        """
        # Fetch thread content first via Jina Reader
        thread_content = await self._fetch_x_thread_content(url)

        # Check for embedded YouTube links
        youtube_urls = self._extract_youtube_urls(thread_content) if thread_content else []

        if youtube_urls:
            logger.info(f"X thread contains {len(youtube_urls)} YouTube URL(s), running parallel analysis")
            # Run Grok (X context) and Gemini (video content) in parallel
            return await self._summarize_x_thread_with_video(url, thread_content, youtube_urls[0])

        # Standard X-only summarization
        return await self._summarize_x_thread_only(url, thread_content)

    async def _summarize_x_thread_only(self, url: str, thread_content: str) -> SummaryResult:
        """Summarize X thread without embedded video (Grok only)"""
        if thread_content:
            prompt = f"""Analyze this X/Twitter post.

X Post URL: {url}

Post Content:
{thread_content}

Provide:
1. title - The poster's actual words. Use their first sentence or main statement (truncate to ~12 words if needed). Do NOT paraphrase or make up a generic title.
2. summary - 2-3 sentences explaining the context and significance
3. key_points - 3-5 bullet points. Include any links from the post using [→](url) format.
4. author - The @handle
5. thread_date - Post date if visible (YYYY-MM-DD)

CRITICAL: The title must be the poster's OWN WORDS from the post, not your interpretation.

Respond in JSON:
{{
    "title": "Poster's actual words from the post...",
    "summary": "...",
    "key_points": ["Point [→](url)", "..."],
    "author": "@handle",
    "thread_date": "YYYY-MM-DD"
}}"""
        else:
            # Fallback if content fetch fails
            prompt = f"""Analyze this X/Twitter post: {url}

Provide:
1. title - The poster's actual words (first sentence or main statement, ~12 words max)
2. summary - 2-3 sentences explaining context
3. key_points - 3-5 bullet points
4. author - @handle
5. thread_date - YYYY-MM-DD if visible

CRITICAL: Title must be the poster's OWN WORDS, not your interpretation.

Respond in JSON:
{{
    "title": "Poster's actual words...",
    "summary": "...",
    "key_points": ["..."],
    "author": "@handle",
    "thread_date": "YYYY-MM-DD"
}}"""

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.xai_key}"
                },
                json={
                    "model": "grok-3-fast",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                },
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # Parse JSON from response
            parsed = self._parse_json_response(content)

            return SummaryResult(
                title=parsed.get("title", "X Thread"),
                summary=parsed.get("summary", content),
                key_points=parsed.get("key_points", []),
                url_type=URLType.X_TWITTER,
                source_url=url,
                extra_metadata={
                    "author": parsed.get("author"),
                    "thread_date": parsed.get("thread_date")
                }
            )

    async def _summarize_x_thread_with_video(self, x_url: str, thread_content: str, youtube_url: str) -> SummaryResult:
        """Parallel summarization: Grok for X context + Gemini for video content"""

        async def grok_x_context():
            """Get X thread context from Grok"""
            prompt = f"""Analyze this X/Twitter post that shares a video. Focus on:
1. A concise title (max 10 words) capturing what the POSTER is saying about the video
2. Who is sharing this and why
3. What context or commentary they provide
4. Why they think this video is worth watching

X Post URL: {x_url}

Post Content:
{thread_content}

Respond in this exact JSON format:
{{
    "title": "Concise title based on what the poster says (not the video title)",
    "poster_context": "What the poster says about the video and why they're sharing it",
    "author": "@handle",
    "thread_date": "YYYY-MM-DD if known"
}}"""

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.xai_key}"
                    },
                    json={
                        "model": "grok-3-fast",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                data = response.json()
                return self._parse_json_response(data["choices"][0]["message"]["content"])

        async def gemini_video_content():
            """Get video analysis from Gemini 2.5 Pro with native YouTube access"""
            # Convert youtu.be to full YouTube URL format
            full_youtube_url = youtube_url
            if 'youtu.be/' in youtube_url:
                video_id = youtube_url.split('youtu.be/')[-1].split('?')[0]
                full_youtube_url = f'https://www.youtube.com/watch?v={video_id}'

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={self.google_api_key}",
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{
                            "parts": [
                                {"text": YOUTUBE_ANALYSIS_PROMPT},
                                {"file_data": {"file_uri": full_youtube_url}}
                            ]
                        }],
                        "generationConfig": {"temperature": 0.3}
                    },
                    timeout=120.0  # Longer timeout for video analysis
                )
                response.raise_for_status()
                data = response.json()
                content = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return self._parse_json_response(content)

        # Run both in parallel
        logger.debug("Running parallel Grok + Gemini analysis")
        x_result, video_result = await asyncio.gather(
            grok_x_context(),
            gemini_video_content(),
            return_exceptions=True
        )

        # Handle exceptions from parallel execution
        if isinstance(x_result, Exception):
            logger.error(f"Grok X context failed: {x_result}")
            x_result = {}
        if isinstance(video_result, Exception):
            logger.error(f"Gemini video analysis failed: {video_result}")
            video_result = {}

        # Merge results into comprehensive summary
        x_title = x_result.get("title", "")
        video_title = video_result.get("title", "Video")
        channel = video_result.get("channel", "Unknown")
        poster_context = x_result.get("poster_context", "")
        video_summary = video_result.get("summary", "")

        # Use X post title (what the poster says), fallback to video title
        merged_title = x_title if x_title else (video_title if video_title != "Video" else "Shared Video")

        # Combined summary: X context + video content
        merged_summary = ""
        if poster_context:
            merged_summary += f"**Shared by {x_result.get('author', 'user')}:** {poster_context}\n\n"
        if video_summary:
            merged_summary += f"**Video ({channel}):** {video_summary}"

        # Combine key points from video
        merged_key_points = video_result.get("key_points", [])

        logger.info(f"Merged X+Video summary: {merged_title}")

        return SummaryResult(
            title=merged_title,
            summary=merged_summary.strip(),
            key_points=merged_key_points,
            url_type=URLType.X_TWITTER,  # Primary URL type is still X
            source_url=x_url,
            extra_metadata={
                "author": x_result.get("author"),
                "thread_date": x_result.get("thread_date"),
                "video_url": youtube_url,
                "video_title": video_title,
                "video_channel": channel,
                "video_duration": video_result.get("duration"),
                "has_embedded_video": True
            }
        )

    async def _summarize_youtube(self, url: str) -> SummaryResult:
        """Use Gemini 2.5 Pro with native YouTube access for video analysis"""
        # Convert youtu.be to full YouTube URL format
        full_youtube_url = url
        if 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[-1].split('?')[0]
            full_youtube_url = f'https://www.youtube.com/watch?v={video_id}'

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={self.google_api_key}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{
                        "parts": [
                            {"text": YOUTUBE_ANALYSIS_PROMPT},
                            {"file_data": {"file_uri": full_youtube_url}}
                        ]
                    }],
                    "generationConfig": {"temperature": 0.3}
                },
                timeout=120.0
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

            parsed = self._parse_json_response(content)

            return SummaryResult(
                title=parsed.get("title", "YouTube Video"),
                summary=parsed.get("summary", content),
                key_points=parsed.get("key_points", []),
                url_type=URLType.YOUTUBE,
                source_url=url,
                extra_metadata={
                    "channel": parsed.get("channel"),
                    "duration": parsed.get("duration")
                }
            )

    async def _fetch_article_content(self, url: str, max_retries: int = 3) -> str:
        """Fetch article content using Jina Reader for clean markdown with retry logic"""
        jina_url = f"https://r.jina.ai/{url}"

        for attempt in range(max_retries):
            logger.debug(f"Fetching content from: {jina_url} (attempt {attempt + 1}/{max_retries})")
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        jina_url,
                        headers={"Accept": "text/markdown"},
                        timeout=30.0,
                        follow_redirects=True
                    )
                    logger.debug(f"Jina response status: {response.status_code}")

                    if response.status_code == 200:
                        content = response.text
                        logger.debug(f"Content fetched, length: {len(content)} chars")
                        # Truncate if too long (keep first ~15k chars for context window)
                        if len(content) > 15000:
                            content = content[:15000] + "\n\n[Content truncated...]"
                        return content
                    elif response.status_code == 429:
                        # Rate limited - wait and retry
                        wait_time = 2 ** attempt  # Exponential backoff: 1, 2, 4 seconds
                        logger.warning(f"Rate limited by Jina Reader, waiting {wait_time}s before retry")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.warning(f"Jina non-200 response ({response.status_code}): {response.text[:200]}")

            except httpx.TimeoutException:
                wait_time = 2 ** attempt
                logger.warning(f"Jina Reader timeout, waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
                    continue
            except Exception as e:
                wait_time = 2 ** attempt
                logger.error(f"Jina Reader fetch failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
                    continue

        logger.error(f"Failed to fetch content after {max_retries} attempts: {url}")
        return ""

    async def _summarize_article(self, url: str) -> SummaryResult:
        """Use Claude Sonnet 4.5 via OpenRouter for articles"""
        # Fetch actual article content first
        article_content = await self._fetch_article_content(url)
        logger.debug(f"Article content fetched: {len(article_content) if article_content else 0} chars")

        if article_content:
            prompt = f"""Analyze this article and provide:
1. A concise title (max 10 words)
2. A 2-3 sentence summary
3. 3-5 key points as bullet points with links to relevant articles/sources if available in the content

Article URL: {url}

Article Content:
{article_content}

IMPORTANT: For key_points, if the content contains links to related articles or sources, include them inline using markdown format. Example:
- Key point about topic [→](https://example.com/article)
- Another point without a link

Respond in this exact JSON format:
{{
    "title": "...",
    "summary": "...",
    "key_points": ["Point with link [→](url)", "Point without link", "..."],
    "author": "if known",
    "publication": "if known"
}}"""
        else:
            # Fallback if content fetch fails
            prompt = f"""Analyze this article/webpage and provide:
1. A concise title (max 10 words)
2. A 2-3 sentence summary
3. 3-5 key points as bullet points with links if you can identify any from the URL

URL: {url}

IMPORTANT: For key_points, if you can identify links to related content, include them inline using markdown format. Example:
- Key point about topic [→](https://example.com/article)
- Another point without a link

Respond in this exact JSON format:
{{
    "title": "...",
    "summary": "...",
    "key_points": ["Point with link [→](url)", "Point without link", "..."],
    "author": "if known",
    "publication": "if known"
}}"""

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.openrouter_key}"
                },
                json={
                    "model": "anthropic/claude-sonnet-4.5",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                },
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            parsed = self._parse_json_response(content)
            
            return SummaryResult(
                title=parsed.get("title", "Article"),
                summary=parsed.get("summary", content),
                key_points=parsed.get("key_points", []),
                url_type=URLType.ARTICLE,
                source_url=url,
                extra_metadata={
                    "author": parsed.get("author"),
                    "publication": parsed.get("publication")
                }
            )

    async def research_topic(self, topic: str, project_name: str = "", 
                              parent_project: str = "", context: str = "") -> ResearchResult:
        """Generate research starter for @note tasks without URLs using Perplexity for web search"""
        
        # Get folder-aware context
        folder_context = self._get_folder_context(project_name, parent_project)
        
        # Combine folder context with any user-provided context
        full_context = folder_context
        if context:
            full_context += f"\n\nAdditional context: {context}"
        
        prompt = f"""Research this topic using current web information and provide a helpful starter note:

Topic: {topic}
Context: {full_context}

IMPORTANT: Search the web and include ACTUAL links you find. Do NOT say "search for X" - instead find and include the real URLs.

Provide:
1. A brief overview (2-3 sentences) with key facts you found
2. 3-5 key facts or points worth knowing
3. 3-5 relevant links you found (official sites, social media, platforms where this entity exists)

For links section, include actual URLs you found such as:
- Official website
- Social media profiles (X/Twitter, Instagram, etc.)
- Platform presence (YouTube, SoundCloud, Spotify, Bandcamp, GitHub, LinkedIn, etc.)
- Wikipedia or other reference pages
- Recent news or articles

Respond in this exact JSON format:
{{
    "summary": "...",
    "key_points": ["...", "...", "..."],
    "links": [
        {{"label": "Official Website", "url": "https://..."}},
        {{"label": "SoundCloud", "url": "https://soundcloud.com/..."}},
        {{"label": "YouTube", "url": "https://youtube.com/..."}}
    ],
    "suggestions": ["Areas to explore further...", "...", "..."]
}}"""

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.perplexity_key}"
                },
                json={
                    "model": "sonar-pro",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                },
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            parsed = self._parse_json_response(content)

            # Validate that we got meaningful content - fail if empty
            if not parsed or not parsed.get("summary"):
                logger.error(f"Perplexity returned empty/unparseable response for topic: {topic}")
                logger.debug(f"Raw Perplexity response: {content[:1500]}")
                raise ValueError(f"Failed to get research content for '{topic}' - API returned empty or unparseable response")

            # Clean citation markers like [1], [3] from Perplexity output
            def clean_citations(text):
                if isinstance(text, str):
                    return re.sub(r'\[\d+\]', '', text).strip()
                return text

            # Convert links array to formatted list as clickable markdown
            links = parsed.get("links", [])
            formatted_links = []
            for link in links:
                if isinstance(link, dict) and link.get("url"):
                    label = link.get("label", "Link")
                    url = link.get("url")
                    formatted_links.append(f"[{label}]({url})")

            return ResearchResult(
                title=topic,
                summary=clean_citations(parsed.get("summary", "")),
                key_points=[clean_citations(p) for p in parsed.get("key_points", [])],
                suggestions=[clean_citations(s) for s in parsed.get("suggestions", [])],
                extra_metadata={
                    "links": formatted_links
                }
            )

    def _validate_links(self, key_points: List[str]) -> List[str]:
        """Validate and clean markdown links in key points"""
        cleaned_points = []
        # Pattern to match markdown links: [text](url)
        link_pattern = re.compile(r'\[([^\]]*)\]\(([^)]*)\)')

        for point in key_points:
            # Find all links in the point
            links = link_pattern.findall(point)
            cleaned_point = point

            for text, url in links:
                # Check if URL is valid (http/https, relative paths, anchors, mailto)
                if url and not url.startswith(('http://', 'https://', '/', '#', 'mailto:')):
                    # Remove invalid link, keep just the text
                    cleaned_point = cleaned_point.replace(f'[{text}]({url})', text)
                    logger.debug(f"Removed invalid link: [{text}]({url})")

            cleaned_points.append(cleaned_point)

        return cleaned_points

    def _parse_json_response(self, content: str) -> dict:
        """Extract JSON from model response and validate links"""
        import json

        result = {}

        # Try direct parse
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # Try to find JSON block
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                except json.JSONDecodeError:
                    logger.warning("Failed to parse JSON from model response")
                    logger.debug(f"Raw content that failed parsing: {content[:1000]}")
                    return {}
            else:
                logger.warning("No JSON block found in model response")
                logger.debug(f"Raw content without JSON: {content[:1000]}")

        # Validate links in key_points if present
        if 'key_points' in result and isinstance(result['key_points'], list):
            result['key_points'] = self._validate_links(result['key_points'])

        return result
