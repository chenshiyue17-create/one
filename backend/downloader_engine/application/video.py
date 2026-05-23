from expansion import Namespace
from application.request import Html

__all__ = ["Video"]


class Video:
    VIDEO_LINK = (
        "video",
        "consumer",
        "originVideoKey",
    )

    @classmethod
    def deal_video_link(
        cls,
        data: Namespace,
        preference="resolution",
    ):
        # 尝试多种可能的视频地址字段
        return (
            cls.generate_video_link(data) 
            or cls.get_video_link(data, preference)
            or [data.safe_extract("video_url")]
            or [data.safe_extract("video_addr")]
            or []
        )

    @classmethod
    def generate_video_link(cls, data: Namespace) -> list:
        # 尝试 originVideoKey 或 origin_video_key
        key = data.safe_extract(".".join(cls.VIDEO_LINK)) or data.safe_extract("video.consumer.origin_video_key")
        return (
            [Html.format_url(f"https://sns-video-bd.xhscdn.com/{key}")]
            if key
            else []
        )

    @classmethod
    def get_video_link(
        cls,
        data: Namespace,
        preference="resolution",
    ) -> list:
        if not (items := cls.get_video_items(data)):
            return []
        match preference:
            case "resolution":
                items.sort(key=lambda x: getattr(x, "height", 0))
            case "bitrate":
                items.sort(key=lambda x: getattr(x, "videoBitrate", getattr(x, "video_bitrate", 0)))
            case "size":
                items.sort(key=lambda x: getattr(x, "size", 0))
            case _:
                raise ValueError(f"Invalid video preference value: {preference}")
        
        best = items[-1]
        url = getattr(best, "masterUrl", getattr(best, "master_url", getattr(best, "url", "")))
        if not url and hasattr(best, "backupUrls") and best.backupUrls:
            url = best.backupUrls[0]
        elif not url and hasattr(best, "backup_urls") and best.backup_urls:
            url = best.backup_urls[0]
            
        return [url] if url else []

    @staticmethod
    def get_video_items(data: Namespace) -> list:
        # 同时尝试不同的路径结构
        stream = data.safe_extract("video.media.stream") or data.safe_extract("video_info.media.stream") or {}
        h264 = getattr(stream, "h264", [])
        h265 = getattr(stream, "h265", [])
        if not isinstance(h264, list): h264 = []
        if not isinstance(h265, list): h265 = []
        return [*h264, *h265]
