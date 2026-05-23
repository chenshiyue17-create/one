from typing import Union
from re import compile
from lxml.etree import HTML
from yaml import safe_load

__all__ = ["Converter"]


class Converter:
    YAML_ILLEGAL = compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
    INITIAL_STATE = "//script/text()"
    PC_KEYS_LINK = (
        "note",
        "noteDetailMap",
        "[-1]",
        "note",
    )
    PHONE_KEYS_LINK = (
        "noteData",
        "data",
        "noteData",
    )

    def run(self, content: str) -> dict:
        return self._filter_object(self._convert_object(self._extract_object(content)))

    def _extract_object(self, html: str) -> str:
        if not html:
            return ""
        html_tree = HTML(html)
        # 尝试查找包含 INITIAL_STATE 的 script 标签，或者带有特定 id 的标签
        scripts = html_tree.xpath("//script/text()")
        
        # 优先查找 window.__INITIAL_STATE__
        for script in reversed(scripts):
            if "window.__INITIAL_STATE__" in script:
                return script
        
        # 备选：查找 rednote 可能会用的其它标识
        for script in reversed(scripts):
            if "initial-state" in script:
                return script
                
        return ""

    @classmethod
    def _convert_object(cls, text: str) -> dict:
        if not text:
            return {}
        # 去掉开头的赋值语句
        if "=" in text:
            text = text.split("=", 1)[1].strip()
        # 去掉结尾的分号
        if text.endswith(";"):
            text = text[:-1].strip()
        
        cleaned = cls.YAML_ILLEGAL.sub("", text)
        try:
            return safe_load(cleaned)
        except Exception:
            # 如果 YAML 解析失败，尝试 JSON 解析
            try:
                import json
                return json.loads(cleaned)
            except Exception:
                return {}

    @classmethod
    def _filter_object(cls, data: dict) -> dict:
        return (
            cls.deep_get(data, cls.PHONE_KEYS_LINK)
            or cls.deep_get(data, cls.PC_KEYS_LINK)
            or {}
        )

    @classmethod
    def deep_get(cls, data: dict, keys: list | tuple, default=None):
        if not data:
            return default
        try:
            for key in keys:
                if key.startswith("[") and key.endswith("]"):
                    data = cls.safe_get(data, int(key[1:-1]))
                else:
                    data = data[key]
            return data
        except (KeyError, IndexError, ValueError, TypeError):
            return default

    @staticmethod
    def safe_get(data: Union[dict, list, tuple, set], index: int):
        if isinstance(data, dict):
            return list(data.values())[index]
        elif isinstance(data, list | tuple | set):
            return data[index]
        raise TypeError

    @staticmethod
    def get_script(scripts: list) -> str:
        scripts.reverse()
        return next(
            (
                script
                for script in scripts
                if script.startswith("window.__INITIAL_STATE__")
            ),
            "",
        )
