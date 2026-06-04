"""
Whisper ASR 封装 — 语音转文字。

功能：
- 自动检测 CUDA GPU
- 多模型大小选择（tiny/base/small/medium/large/turbo）
- 支持中文语言强制指定
- 批处理接口
"""

import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 支持的模型及大小
MODEL_SIZES = ['tiny', 'base', 'small', 'medium', 'large', 'turbo']
DEFAULT_MODEL = 'small'


def detect_gpu() -> bool:
    """检测是否有可用的 CUDA GPU。"""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


class WhisperASR:
    """Whisper 语音转文字封装。"""

    def __init__(self, model_size: str = DEFAULT_MODEL, language: str = 'zh'):
        """
        Args:
            model_size: 模型大小 (tiny/base/small/medium/large/turbo)
            language: 语言代码，'zh' 为中文
        """
        if model_size not in MODEL_SIZES:
            raise ValueError(f"不支持的模型大小: {model_size}，可选: {MODEL_SIZES}")

        self.model_size = model_size
        self.language = language
        self._model = None
        self._device = 'cuda' if detect_gpu() else 'cpu'

    def load(self):
        """加载模型（首次调用时自动加载）。"""
        if self._model is not None:
            return

        logger.info(f"加载 Whisper 模型: {self.model_size} (device={self._device})")
        try:
            import whisper
            self._model = whisper.load_model(self.model_size, device=self._device)
            logger.info(f"模型加载完成")
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise

    def transcribe(self, audio_path: str | Path) -> dict:
        """转写单个音频文件。

        Args:
            audio_path: 音频文件路径（支持 mp3/wav/m4a/flac 等）

        Returns:
            {
                'text': str,           # 完整文本
                'segments': [          # 分段
                    {'start': float, 'end': float, 'text': str},
                    ...
                ],
                'language': str,       # 检测到的语言
            }
        """
        self.load()
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        logger.info(f"转写: {audio_path.name}")
        result = self._model.transcribe(
            str(audio_path),
            language=self.language,
            verbose=False,
        )

        segments = [
            {'start': seg['start'], 'end': seg['end'], 'text': seg['text'].strip()}
            for seg in result.get('segments', [])
        ]

        output = {
            'text': result['text'].strip(),
            'segments': segments,
            'language': result.get('language', self.language),
        }

        # 统计信息
        duration = segments[-1]['end'] if segments else 0
        logger.info(f"转写完成: {len(output['text'])} 字, {len(segments)} 段, {duration:.0f}s")

        return output

    def transcribe_batch(self, audio_dir: str | Path, pattern: str = '*.m4a') -> dict:
        """批量转写目录中的音频文件。

        Args:
            audio_dir: 音频文件目录
            pattern: 文件匹配模式

        Returns:
            {filename: transcribe_result} 字典
        """
        audio_dir = Path(audio_dir)
        audio_files = list(audio_dir.glob(pattern))

        if not audio_files:
            logger.warning(f"在 {audio_dir} 中未找到匹配 {pattern} 的文件")
            return {}

        logger.info(f"批量转写: {len(audio_files)} 个文件")
        results = {}
        for i, audio_path in enumerate(audio_files):
            logger.info(f"[{i + 1}/{len(audio_files)}] {audio_path.name}")
            try:
                results[audio_path.name] = self.transcribe(audio_path)
            except Exception as e:
                logger.error(f"转写失败 {audio_path.name}: {e}")
                results[audio_path.name] = {'error': str(e)}

        return results

    @property
    def device(self) -> str:
        return self._device


def get_optimal_model_size() -> str:
    """根据硬件自动选择最优模型大小。

    Returns:
        推荐的模型大小名称
    """
    if detect_gpu():
        try:
            import torch
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            if vram_gb >= 10:
                return 'turbo'  # 最佳精度+速度
            elif vram_gb >= 6:
                return 'medium'
            elif vram_gb >= 4:
                return 'small'
            else:
                return 'base'
        except Exception:
            return 'small'
    else:
        # CPU：推荐 small 作为平衡选择
        return 'small'
