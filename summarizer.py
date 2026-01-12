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


class AISummarizer:
    def __init__(self):
        self.xai_key = os.getenv("XAI_API_KEY")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        
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

    async def _summarize_x_thread(self, url: str) -> SummaryResult:
        """Use Grok to analyze pre-fetched X/Twitter thread content"""
        # Fetch thread content first via Jina Reader
        thread_content = await self._fetch_x_thread_content(url)

        if thread_content:
            prompt = f"""Analyze this X/Twitter post and provide:
1. A concise title (max 10 words) capturing the main topic
2. A 2-3 sentence summary of what the post says
3. 3-5 key points as bullet points with links if the post references external URLs

X Post URL: {url}

Post Content:
{thread_content}

IMPORTANT: For key_points, if the post contains links to articles, videos, or other content, include them inline using markdown format. Example:
- Key point about topic [→](https://example.com/article)
- Another point without a link

Respond in this exact JSON format:
{{
    "title": "...",
    "summary": "...",
    "key_points": ["Point with link [→](url)", "Point without link", "..."],
    "author": "@handle",
    "thread_date": "YYYY-MM-DD if known"
}}"""
        else:
            # Fallback if content fetch fails
            prompt = f"""Analyze this X/Twitter post: {url}

Provide:
1. A concise title (max 10 words)
2. A 2-3 sentence summary
3. 3-5 key points

Respond in JSON format:
{{
    "title": "...",
    "summary": "...",
    "key_points": ["...", "..."],
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

    async def _summarize_youtube(self, url: str) -> SummaryResult:
        """Use Gemini 3 Flash via OpenRouter for YouTube videos"""
        prompt = f"""Analyze this YouTube video and provide:
1. The exact video title
2. The channel name
3. A 2-3 sentence summary of the content
4. 3-5 key points as bullet points with links if the video references external resources

Video URL: {url}

IMPORTANT: For key_points, if the video mentions or links to articles, tools, resources, or other videos, include them inline using markdown format. Example:
- Key point about topic [→](https://example.com/resource)
- Another point without a link

Respond in this exact JSON format:
{{
    "title": "...",
    "channel": "...",
    "summary": "...",
    "key_points": ["Point with link [→](url)", "Point without link", "..."],
    "duration": "if known"
}}"""

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.openrouter_key}"
                },
                json={
                    "model": "google/gemini-3-flash-preview",
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
        """Generate research starter for @note tasks without URLs"""
        
        # Get folder-aware context
        folder_context = self._get_folder_context(project_name, parent_project)
        
        # Combine folder context with any user-provided context
        full_context = folder_context
        if context:
            full_context += f"\n\nAdditional context: {context}"
        
        prompt = f"""Research this topic and provide a helpful starter note:

Topic: {topic}
Context: {full_context}

Provide:
1. A brief overview (2-3 sentences)
2. 3-5 key facts or points worth knowing
3. 3-5 suggested areas to explore or questions to research

Respond in this exact JSON format:
{{
    "summary": "...",
    "key_points": ["...", "...", "..."],
    "suggestions": ["...", "...", "..."]
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
                    "temperature": 0.5
                },
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            parsed = self._parse_json_response(content)
            
            return ResearchResult(
                title=topic,
                summary=parsed.get("summary", ""),
                key_points=parsed.get("key_points", []),
                suggestions=parsed.get("suggestions", [])
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
                    return {}

        # Validate links in key_points if present
        if 'key_points' in result and isinstance(result['key_points'], list):
            result['key_points'] = self._validate_links(result['key_points'])

        return result
