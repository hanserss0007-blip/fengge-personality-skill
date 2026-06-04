"""
下载管理器 — Queue + Thread 并发下载。

复用 ABIDE 数据下载项目（01_download_abide.py）的成熟模式：
- threading.Thread 工作池
- queue.Queue 任务队列
- 3 次重试 + 指数退避
- tqdm 进度条
- 临时文件 + 原子重命名
"""

import os
import time
import queue
import threading
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class DownloadTask:
    """下载任务描述。"""

    def __init__(self, task_id: str, url: str, dest_path: Path, metadata: dict = None):
        self.task_id = task_id
        self.url = url
        self.dest_path = Path(dest_path)
        self.metadata = metadata or {}


class DownloadManager:
    """多线程下载管理器。

    Args:
        num_threads: 并发线程数（默认 3，B站/YouTube 友好）
        max_retries: 每个任务最大重试次数
        retry_delay_base: 重试延迟基数（秒），指数退避 = base * 2^attempt
    """

    def __init__(self, num_threads: int = 3, max_retries: int = 3, retry_delay_base: float = 5.0):
        self.num_threads = num_threads
        self.max_retries = max_retries
        self.retry_delay_base = retry_delay_base
        self._task_queue: queue.Queue = queue.Queue()
        self._results: dict = {}
        self._results_lock = threading.Lock()
        self._stop_event = threading.Event()

    def add_task(self, task: DownloadTask):
        """添加下载任务到队列。"""
        self._task_queue.put(task)

    def add_tasks(self, tasks: list):
        """批量添加下载任务。"""
        for t in tasks:
            self.add_task(t)

    def _worker(self, worker_id: int, download_fn: Callable):
        """工作线程。

        Args:
            worker_id: 线程编号
            download_fn: 下载函数，签名为 fn(task: DownloadTask) -> bool
        """
        while not self._stop_event.is_set():
            try:
                task = self._task_queue.get(timeout=1)
            except queue.Empty:
                break

            success = False
            last_error = None

            for attempt in range(self.max_retries):
                if self._stop_event.is_set():
                    break
                try:
                    # 确保目标目录存在
                    task.dest_path.parent.mkdir(parents=True, exist_ok=True)

                    # 下载到临时文件
                    tmp_suffix = task.dest_path.suffix or '.tmp'
                    with tempfile.NamedTemporaryFile(
                        dir=task.dest_path.parent,
                        prefix=f'.{task.task_id}_',
                        suffix=tmp_suffix,
                        delete=False
                    ) as tmp:
                        tmp_path = Path(tmp.name)

                    # 执行下载
                    result = download_fn(task, tmp_path)

                    if result:
                        # 原子重命名
                        shutil.move(str(tmp_path), str(task.dest_path))
                        success = True
                        break
                    else:
                        # 下载函数返回 False
                        tmp_path.unlink(missing_ok=True)
                        last_error = Exception("download_fn returned False")

                except Exception as e:
                    last_error = e
                    tmp_path.unlink(missing_ok=True) if 'tmp_path' in dir() else None
                    if attempt < self.max_retries - 1:
                        wait = self.retry_delay_base * (2 ** attempt)
                        logger.warning(
                            f"[Worker {worker_id}] {task.task_id} 失败 "
                            f"(尝试 {attempt + 1}/{self.max_retries})，"
                            f"{wait:.0f}s 后重试: {e}"
                        )
                        # 分段等待，以便响应停止信号
                        for _ in range(int(wait)):
                            if self._stop_event.is_set():
                                break
                            time.sleep(1)
                    else:
                        logger.error(
                            f"[Worker {worker_id}] {task.task_id} 最终失败: {e}"
                        )

            with self._results_lock:
                self._results[task.task_id] = {
                    'success': success,
                    'dest': str(task.dest_path) if success else None,
                    'error': str(last_error) if last_error else None,
                    'metadata': task.metadata,
                }

            self._task_queue.task_done()

    def run(self, download_fn: Callable, progress_desc: str = "下载") -> dict:
        """启动工作线程并等待完成。

        Args:
            download_fn: 下载函数 fn(task: DownloadTask, tmp_path: Path) -> bool
            progress_desc: 进度描述

        Returns:
            {task_id: {success, dest, error, metadata}} 字典
        """
        total = self._task_queue.qsize()
        if total == 0:
            logger.warning("任务队列为空，无需下载")
            return {}

        logger.info(f"开始 {progress_desc}：共 {total} 个任务，{self.num_threads} 个线程")

        threads = []
        for i in range(self.num_threads):
            t = threading.Thread(target=self._worker, args=(i, download_fn), daemon=True)
            t.start()
            threads.append(t)

        # 等待队列清空
        try:
            from tqdm import tqdm
            pbar = tqdm(total=total, desc=progress_desc, unit='task')
            last_done = 0
            while True:
                current_done = total - self._task_queue.qsize()
                if current_done > last_done:
                    pbar.update(current_done - last_done)
                    last_done = current_done
                if current_done >= total:
                    break
                time.sleep(0.5)
            pbar.close()
        except ImportError:
            # 无 tqdm 时的简单等待
            self._task_queue.join()

        # 等待所有线程结束
        for t in threads:
            t.join(timeout=5)

        success_count = sum(1 for r in self._results.values() if r['success'])
        logger.info(f"{progress_desc} 完成：{success_count}/{total} 成功")

        return dict(self._results)

    def stop(self):
        """停止所有工作线程。"""
        self._stop_event.set()
