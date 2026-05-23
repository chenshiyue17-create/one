from expansion import Namespace

from application.request import Html

__all__ = ["Image"]


class Image:
    @classmethod
    def get_image_link(cls, data: Namespace, format_: str) -> tuple[list, list]:
        images = data.safe_extract("imageList", [])
        live_link = cls.__get_live_link(images)
        if not any(
            token_list := [
                cls.__extract_image_token(Namespace.object_extract(i, "urlDefault"))
                for i in images
            ]
        ):
            token_list = [
                cls.__extract_image_token(Namespace.object_extract(i, "url"))
                for i in images
            ]
        match format_:
            case "png" | "webp" | "jpeg" | "heic" | "avif":
                return [
                    Html.format_url(
                        cls.__generate_fixed_link(
                            i,
                            format_,
                        )
                    )
                    for i in token_list
                ], live_link
            case "auto":
                return [
                    Html.format_url(cls.__generate_auto_link(i)) for i in token_list
                ], live_link
            case _:
                raise ValueError

    @staticmethod
    def __generate_auto_link(token: str) -> str:
        return f"https://sns-img-bd.xhscdn.com/{token}"

    @staticmethod
    def __generate_fixed_link(
        token: str,
        format_: str,
    ) -> str:
        return f"https://ci.xiaohongshu.com/{token}?imageView2/format/{format_}"

    @staticmethod
    def __extract_image_token(url: str) -> str:
        if not url:
            return ""
        # 兼容多种 URL 格式，提取 ID 部分
        # 如 https://sns-img-al.xhscdn.com/1040g008317...!nd_v1_tplv_q90.jpg
        # 或 https://ci.xiaohongshu.com/spectrum/1040g...
        path = url.split("?")[0].split("!")[0]
        parts = path.split("/")
        if len(parts) > 3:
            return parts[-1]
        return ""

    @staticmethod
    def __get_live_link(items: list) -> list:
        return [
            (
                Html.format_url(
                    Namespace.object_extract(item, "stream.h264[0].masterUrl")
                )
                or None
            )
            for item in items
        ]
