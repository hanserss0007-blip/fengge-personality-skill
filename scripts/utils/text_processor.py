"""
文本处理器 — 中文分词、清洗、特征提取。

功能：
- jieba 分词 + 自定义词典
- 中文停用词过滤
- 文本正则化（全角/半角、特殊字符）
- n-gram 提取
- 口头禅挖掘（TF-IDF + 频率）
"""

import re
import logging
from pathlib import Path
from typing import Optional
from collections import Counter

logger = logging.getLogger(__name__)

# 中文标点符号
CN_PUNCTUATION = set('，。！？、；：""''（）【】《》…—·～「」『』')

# 基础停用词（部分列表，jieba 自带更完整）
STOP_WORDS_BASIC = {
    '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一',
    '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着',
    '没有', '看', '好', '自己', '这', '他', '她', '它', '们', '那', '那个',
    '这个', '什么', '怎么', '哪', '为什么', '因为', '所以', '但是', '然后',
    '就是', '可以', '还是', '如果', '的话', '吧', '嘛', '呢', '啊', '哦', '嗯',
    '哈', '哈哈', '哈哈哈', '卧槽', '牛逼',
}


class TextProcessor:
    """中文文本处理器。"""

    def __init__(self, custom_dict: Optional[str | Path] = None, stop_words: set = None):
        """
        Args:
            custom_dict: 自定义词典路径（每行一个词）
            stop_words: 自定义停用词集合（None 则使用默认）
        """
        self._init_jieba()
        if custom_dict:
            self._load_custom_dict(custom_dict)
        self.stop_words = stop_words if stop_words is not None else STOP_WORDS_BASIC.copy()

    def _init_jieba(self):
        """初始化 jieba 分词器。"""
        try:
            import jieba
            jieba.initialize()
            self._jieba = jieba
        except Exception as e:
            logger.error(f"jieba 初始化失败: {e}")
            raise

    def _load_custom_dict(self, dict_path: str | Path):
        """加载自定义词典。"""
        dict_path = Path(dict_path)
        if dict_path.exists():
            self._jieba.load_userdict(str(dict_path))
            logger.info(f"加载自定义词典: {dict_path}")

    @staticmethod
    def normalize(text: str) -> str:
        """文本正则化。

        - 全角字符转半角
        - 移除多余空白
        - 移除控制字符
        - 保留中文标点

        Args:
            text: 原始文本

        Returns:
            正则化后的文本
        """
        # 移除控制字符（保留换行）
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        # 全角空格转半角
        text = text.replace('　', ' ')
        # 合并多个空白
        text = re.sub(r' +', ' ', text)
        # 合并多个换行
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    @staticmethod
    def clean_for_analysis(text: str) -> str:
        """清洗文本用于分析。

        - 移除纯表情/符号行
        - 移除纯数字行
        - 移除过短行（<2字）
        - 保留中英文混合内容

        Args:
            text: 原始文本

        Returns:
            清洗后的文本
        """
        lines = text.split('\n')
        cleaned = []
        for line in lines:
            line = line.strip()
            # 跳过空行
            if not line:
                continue
            # 跳过纯数字行
            if re.match(r'^[\d\s\.\,\+\-\%]+$', line):
                continue
            # 跳过过短行
            if len(line) < 2:
                continue
            # 跳过纯符号行
            chinese_chars = len(re.findall(r'[一-鿿]', line))
            if chinese_chars == 0 and len(re.findall(r'[a-zA-Z]', line)) < 3:
                continue
            cleaned.append(line)
        return '\n'.join(cleaned)

    def tokenize(self, text: str, remove_stop: bool = True) -> list[str]:
        """分词。

        Args:
            text: 输入文本
            remove_stop: 是否去除停用词

        Returns:
            词语列表
        """
        words = self._jieba.lcut(text)
        words = [w.strip() for w in words if w.strip() and w not in CN_PUNCTUATION]
        if remove_stop:
            words = [w for w in words if w not in self.stop_words and len(w) > 1]
        return words

    def get_word_frequency(self, texts: list[str], top_n: int = 100) -> list[tuple[str, int]]:
        """词频统计。

        Args:
            texts: 文本列表
            top_n: 返回前 N 个高频词

        Returns:
            [(词, 频次)] 列表，按频次降序
        """
        counter = Counter()
        for text in texts:
            words = self.tokenize(text)
            counter.update(words)
        return counter.most_common(top_n)

    def get_ngrams(self, text: str, n: int = 3, min_freq: int = 5) -> list[tuple[str, int]]:
        """提取 n-gram 短语。

        Args:
            text: 输入文本
            n: n-gram 的 n
            min_freq: 最小频率阈值

        Returns:
            [(短语, 频次)] 列表
        """
        words = self.tokenize(text, remove_stop=False)
        counter = Counter()
        for i in range(len(words) - n + 1):
            ngram = ''.join(words[i:i + n])
            counter[ngram] += 1
        return [(ngram, freq) for ngram, freq in counter.most_common() if freq >= min_freq]

    def find_catchphrases(
        self, texts: list[str], n_range: tuple[int, int] = (2, 6), top_n: int = 20
    ) -> list[dict]:
        """发现口头禅。

        结合频率和 TF-IDF 显著性找出最有特征性的短语。

        Args:
            texts: 文本列表（每个元素为一句话或一段落）
            n_range: n-gram 范围
            top_n: 返回前 N 个

        Returns:
            [{'phrase': str, 'count': int, 'score': float}] 按 score 降序
        """
        from sklearn.feature_extraction.text import TfidfVectorizer

        # 对所有文本分词（不去停用词，保留短语结构）
        tokenized = [' '.join(self.tokenize(t, remove_stop=False)) for t in texts if t.strip()]

        # TF-IDF
        try:
            vectorizer = TfidfVectorizer(
                ngram_range=n_range,
                max_features=5000,
                token_pattern=r'(?u)\b\w+\b',  # 中文字符模式
            )
            tfidf_matrix = vectorizer.fit_transform(tokenized)
            feature_names = vectorizer.get_feature_names_out()

            # 计算每个 n-gram 的总 TF-IDF 分数
            scores = tfidf_matrix.sum(axis=0).A1
            phrase_scores = list(zip(feature_names, scores))
            phrase_scores.sort(key=lambda x: x[1], reverse=True)

            # 同时统计原始频率
            word_freq = self.get_word_frequency([' '.join(self.tokenize(t, remove_stop=False))
                                                  for t in texts], top_n=len(feature_names))
            freq_map = dict(word_freq)

            results = []
            for phrase, score in phrase_scores[:top_n * 2]:
                count = freq_map.get(phrase, 0)
                if count >= 3 and len(phrase) >= 2:
                    results.append({'phrase': phrase, 'count': count, 'score': float(score)})

            return results[:top_n]

        except Exception as e:
            logger.warning(f"TF-IDF 口头禅挖掘失败: {e}，回退到简单频率")
            word_freq = self.get_word_frequency(
                [' '.join(self.tokenize(t, remove_stop=False)) for t in texts], top_n=top_n
            )
            return [{'phrase': w, 'count': c, 'score': float(c)} for w, c in word_freq]

    def sentence_stats(self, texts: list[str]) -> dict:
        """句子统计。

        Args:
            texts: 句子列表

        Returns:
            {
                'total': int,           # 总句数
                'total_chars': int,     # 总字数（中文）
                'avg_len': float,       # 平均句长
                'med_len': float,       # 中位句长
                'std_len': float,       # 句长标准差
                'len_distribution': {   # 句长分布
                    'short (<10)': int,
                    'medium (10-30)': int,
                    'long (30-60)': int,
                    'very_long (>60)': int,
                },
            }
        """
        import statistics

        lengths = [len(re.findall(r'[一-鿿]', t)) for t in texts if t.strip()]
        total_chars = sum(lengths)

        if not lengths:
            return {'total': 0, 'total_chars': 0, 'avg_len': 0, 'med_len': 0,
                    'std_len': 0, 'len_distribution': {}}

        return {
            'total': len(lengths),
            'total_chars': total_chars,
            'avg_len': round(sum(lengths) / len(lengths), 1),
            'med_len': round(statistics.median(lengths), 1),
            'std_len': round(statistics.stdev(lengths), 1) if len(lengths) > 1 else 0,
            'len_distribution': {
                'short (<10)': sum(1 for l in lengths if l < 10),
                'medium (10-30)': sum(1 for l in lengths if 10 <= l <= 30),
                'long (30-60)': sum(1 for l in lengths if 30 < l <= 60),
                'very_long (>60)': sum(1 for l in lengths if l > 60),
            },
        }
