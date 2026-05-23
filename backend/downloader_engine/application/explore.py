from datetime import datetime

from expansion import Namespace
from translation import _

__all__ = ["Explore"]


class Explore:
    time_format = "%Y-%m-%d_%H:%M:%S"

    def run(self, data: Namespace) -> dict:
        return self.__extract_data(data)

    def __extract_data(self, data: Namespace) -> dict:
        result = {}
        if data:
            self.__extract_interact_info(result, data)
            self.__extract_tags(result, data)
            self.__extract_info(result, data)
            self.__extract_time(result, data)
            self.__extract_user(result, data)
        return result

    @staticmethod
    def __extract_interact_info(container: dict, data: Namespace) -> None:
        container["收藏数量"] = data.safe_extract("interactInfo.collectedCount") or data.safe_extract("interact_info.collected_count") or "0"
        container["评论数量"] = data.safe_extract("interactInfo.commentCount") or data.safe_extract("interact_info.comment_count") or "0"
        container["分享数量"] = data.safe_extract("interactInfo.shareCount") or data.safe_extract("interact_info.share_count") or "0"
        container["点赞数量"] = data.safe_extract("interactInfo.likedCount") or data.safe_extract("interact_info.liked_count") or "0"

    @staticmethod
    def __extract_tags(container: dict, data: Namespace):
        tags = data.safe_extract("tagList") or data.safe_extract("tag_list") or []
        container["作品标签"] = " ".join(
            Namespace.object_extract(i, "name") for i in tags
        )

    def __extract_info(self, container: dict, data: Namespace):
        container["作品ID"] = data.safe_extract("noteId") or data.safe_extract("note_id")
        # 兼容 rednote.com
        container["作品链接"] = (
            f"https://www.rednote.com/explore/{container['作品ID']}"
        )
        container["作品标题"] = data.safe_extract("title") or data.safe_extract("display_title")
        container["作品描述"] = data.safe_extract("desc")
        container["作品类型"] = self.__classify_works(data)
        
        # 提取封面地址
        images = data.safe_extract("imageList") or data.safe_extract("image_list") or []
        if images:
            # 优先取 urlDefault
            cover = Namespace.object_extract(images[0], "urlDefault") or Namespace.object_extract(images[0], "url") or Namespace.object_extract(images[0], "url_default")
            container["封面地址"] = cover
        else:
            container["封面地址"] = ""

    def __extract_time(self, container: dict, data: Namespace):
        container["发布时间"] = (
            datetime.fromtimestamp(time / 1000).strftime(self.time_format)
            if (time := (data.safe_extract("time") or data.safe_extract("create_time")))
            else _("未知")
        )
        container["最后更新时间"] = (
            datetime.fromtimestamp(last / 1000).strftime(self.time_format)
            if (last := (data.safe_extract("lastUpdateTime") or data.safe_extract("last_update_time")))
            else _("未知")
        )
        container["时间戳"] = (
            (time / 1000) if (time := (data.safe_extract("time") or data.safe_extract("create_time"))) else None
        )

    @staticmethod
    def __extract_user(container: dict, data: Namespace):
        user = data.safe_extract("user") or {}
        container["作者昵称"] = Namespace.object_extract(user, "nickname") or Namespace.object_extract(user, "nickName")
        container["作者ID"] = Namespace.object_extract(user, "userId") or Namespace.object_extract(user, "user_id")
        container["作者链接"] = (
            f"https://www.rednote.com/user/profile/{container['作者ID']}"
        )

    @staticmethod
    def __classify_works(data: Namespace) -> str:
        type_ = data.safe_extract("type") or data.safe_extract("model_type")
        list_ = data.safe_extract("imageList") or data.safe_extract("image_list") or []
        if type_ not in {"video", "normal", "note"} or len(list_) == 0:
            if type_ == "video": return _("视频") # 即使没有 imageList，如果是 video 也可以尝试
            return _("图文") # 默认为图文
        if type_ == "video":
            return _("视频")
        return _("图文")
