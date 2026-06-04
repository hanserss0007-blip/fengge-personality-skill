"""
B站 API 客户端封装。

基于 bilibili-api-python，提供统一的接口：
- 搜索视频/UP主
- 获取视频信息、弹幕、评论
- 内置速率限制和错误重试
"""

import asyncio
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class BilibiliClient:
    """B站 API 客户端，封装常用操作和速率限制。"""

    def __init__(self, rate_limit: float = 1.0, max_retries: int = 3):
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self._last_request = 0.0
        self._credential_obj = None

    def _get_credential(self):
        """获取 Credential 实例（懒加载）。"""
        if self._credential_obj is None:
            from bilibili_api import Credential
            self._credential_obj = Credential()
        return self._credential_obj

    async def _rate_limit_wait(self):
        """速率限制等待。"""
        elapsed = time.time() - self._last_request
        if elapsed < self.rate_limit:
            await asyncio.sleep(self.rate_limit - elapsed)
        self._last_request = time.time()

    async def _retry_request(self, coro_factory, desc: str = "request"):
        """带重试的请求包装器。每次重试创建新协程，避免 reuse 错误。"""
        for attempt in range(self.max_retries):
            try:
                await self._rate_limit_wait()
                result = await coro_factory()
                return result
            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait = 2 ** attempt * 5
                    logger.warning(
                        f"{desc} 失败 (尝试 {attempt + 1}/{self.max_retries})，{wait}s 后重试: {e}"
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"{desc} 最终失败: {e}")
                    raise

    # ---- 用户相关 ----

    async def get_user_info(self, uid: int) -> dict:
        """获取 UP 主信息。"""
        from bilibili_api import user
        cred = self._get_credential()
        u = user.User(uid=uid, credential=cred)
        return await self._retry_request(lambda: u.get_user_info(), f"get_user_info({uid})")

    async def get_user_videos(self, uid: int, page: int = 1, page_size: int = 50) -> dict:
        """获取 UP 主视频列表。"""
        from bilibili_api import user
        cred = self._get_credential()
        u = user.User(uid=uid, credential=cred)
        return await self._retry_request(
            lambda: u.get_videos(ps=page_size, pn=page), f"get_videos(uid={uid}, p={page})"
        )

    # ---- 视频相关 ----

    async def get_video_info(self, bvid: str) -> dict:
        """获取视频详细信息。"""
        from bilibili_api import video
        cred = self._get_credential()
        v = video.Video(bvid=bvid, credential=cred)
        return await self._retry_request(lambda: v.get_info(), f"get_video_info({bvid})")

    async def get_danmakus(self, bvid: str, page_index: int = 0) -> list:
        """获取视频弹幕列表。"""
        from bilibili_api import video
        cred = self._get_credential()
        v = video.Video(bvid=bvid, credential=cred)
        return await self._retry_request(
            lambda: v.get_danmakus(page_index=page_index), f"get_danmakus({bvid})"
        )

    async def get_comments(self, bvid: str, page: int = 1, sort: int = 2) -> dict:
        """获取视频评论。"""
        from bilibili_api import video
        cred = self._get_credential()
        v = video.Video(bvid=bvid, credential=cred)
        return await self._retry_request(
            lambda: v.get_comments(page_index=page, order=sort), f"get_comments({bvid}, p={page})"
        )

    # ---- 搜索相关 ----

    async def search_user(self, keyword: str, page: int = 1) -> dict:
        """搜索 UP 主。"""
        from bilibili_api import search
        return await self._retry_request(
            lambda: search.search_by_type(
                keyword, search_type=search.SearchObjectType.USER, page=page
            ),
            f"search_user({keyword})"
        )

    async def search_video(self, keyword: str, page: int = 1, page_size: int = 20) -> dict:
        """搜索视频。"""
        from bilibili_api import search
        return await self._retry_request(
            lambda: search.search_by_type(
                keyword, search_type=search.SearchObjectType.VIDEO, page=page
            ),
            f"search_video({keyword})"
        )


# 全局单例
_client: Optional[BilibiliClient] = None


def get_client(rate_limit: float = 1.0) -> BilibiliClient:
    """获取全局 BilibiliClient 单例。"""
    global _client
    if _client is None:
        _client = BilibiliClient(rate_limit=rate_limit)
    return _client
