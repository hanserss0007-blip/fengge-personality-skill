"""
进度追踪器 — 断点续传支持。

提供基于 JSON manifest 的进度记录，允许流水线在中断后从上次位置恢复。
"""

import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ProgressTracker:
    """流水线进度追踪器。

    使用 JSON 文件记录每个阶段的完成状态和中间数据，
    支持断点续传和增量更新。
    """

    def __init__(self, manifest_path: str | Path):
        """
        Args:
            manifest_path: manifest JSON 文件路径
        """
        self.manifest_path = Path(manifest_path)
        self._data = self._load()

    def _load(self) -> dict:
        """加载 manifest，文件不存在则创建空状态。"""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"加载进度文件: {self.manifest_path}")
                return data
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"进度文件损坏，重置: {e}")

        return {
            'pipeline_version': '0.1.0',
            'created_at': datetime.now().isoformat(),
            'phases': {},
        }

    def save(self):
        """保存 manifest 到磁盘。"""
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self._data['updated_at'] = datetime.now().isoformat()
        with open(self.manifest_path, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    # ---- 阶段管理 ----

    def start_phase(self, phase_name: str):
        """标记阶段开始。"""
        if phase_name not in self._data['phases']:
            self._data['phases'][phase_name] = {
                'status': 'started',
                'started_at': datetime.now().isoformat(),
                'completed_items': [],
                'total_items': 0,
                'errors': [],
            }
        else:
            self._data['phases'][phase_name]['status'] = 'started'
            self._data['phases'][phase_name]['started_at'] = datetime.now().isoformat()
        self.save()

    def complete_phase(self, phase_name: str):
        """标记阶段完成。"""
        if phase_name in self._data['phases']:
            self._data['phases'][phase_name]['status'] = 'completed'
            self._data['phases'][phase_name]['completed_at'] = datetime.now().isoformat()
            self.save()

    def fail_phase(self, phase_name: str, error: str):
        """标记阶段失败。"""
        if phase_name in self._data['phases']:
            self._data['phases'][phase_name]['status'] = 'failed'
            self._data['phases'][phase_name]['errors'].append({
                'message': error,
                'time': datetime.now().isoformat(),
            })
            self.save()

    def is_phase_completed(self, phase_name: str) -> bool:
        """检查阶段是否已完成。"""
        return (
            phase_name in self._data['phases']
            and self._data['phases'][phase_name].get('status') == 'completed'
        )

    # ---- 条目管理 ----

    def set_total_items(self, phase_name: str, total: int):
        """设置阶段的条目总数。"""
        if phase_name not in self._data['phases']:
            self._data['phases'][phase_name] = {
                'status': 'pending',
                'completed_items': [],
                'total_items': total,
                'errors': [],
            }
        else:
            self._data['phases'][phase_name]['total_items'] = total
        self.save()

    def mark_item_completed(self, phase_name: str, item_id: str):
        """标记单个条目完成（去重）。"""
        if phase_name not in self._data['phases']:
            self._data['phases'][phase_name] = {
                'status': 'started',
                'completed_items': [],
                'total_items': 0,
                'errors': [],
            }
        items = self._data['phases'][phase_name]['completed_items']
        if item_id not in items:
            items.append(item_id)
            self.save()

    def is_item_completed(self, phase_name: str, item_id: str) -> bool:
        """检查条目是否已完成。"""
        if phase_name not in self._data['phases']:
            return False
        return item_id in self._data['phases'][phase_name].get('completed_items', [])

    def get_pending_items(self, phase_name: str, all_items: list[str]) -> list[str]:
        """获取尚未完成的条目列表。"""
        completed = set(
            self._data['phases'].get(phase_name, {}).get('completed_items', [])
        )
        return [item for item in all_items if item not in completed]

    # ---- 进度查询 ----

    def get_progress(self, phase_name: str) -> dict:
        """获取指定阶段的进度信息。"""
        phase = self._data['phases'].get(phase_name, {})
        completed = len(phase.get('completed_items', []))
        total = phase.get('total_items', 0)
        return {
            'phase': phase_name,
            'status': phase.get('status', 'not_started'),
            'completed': completed,
            'total': total,
            'pct': round(completed / total * 100, 1) if total > 0 else 0,
            'errors': len(phase.get('errors', [])),
        }

    def get_all_progress(self) -> dict:
        """获取所有阶段的进度快照。"""
        return {
            phase: self.get_progress(phase)
            for phase in self._data.get('phases', {})
        }

    # ---- 数据存取 ----

    def set_phase_data(self, phase_name: str, key: str, value):
        """在阶段存储中保存任意数据。"""
        if phase_name not in self._data['phases']:
            self._data['phases'][phase_name] = {
                'status': 'pending',
                'completed_items': [],
                'total_items': 0,
                'errors': [],
                'data': {},
            }
        if 'data' not in self._data['phases'][phase_name]:
            self._data['phases'][phase_name]['data'] = {}
        self._data['phases'][phase_name]['data'][key] = value
        self.save()

    def get_phase_data(self, phase_name: str, key: str = None):
        """获取阶段存储中的数据。"""
        data = self._data.get('phases', {}).get(phase_name, {}).get('data', {})
        if key:
            return data.get(key)
        return data
