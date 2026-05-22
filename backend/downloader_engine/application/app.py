from asyncio import (
    Event,
    Queue,
    QueueEmpty,
    Semaphore,
    create_task,
    gather,
    sleep,
    Future,
    CancelledError,
)
from contextlib import suppress
from datetime import datetime
from re import compile
from urllib.parse import urlparse
from textwrap import dedent
from fastapi import FastAPI
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import subprocess
import os
from fastmcp import FastMCP
from typing import Annotated
from pydantic import Field
from types import SimpleNamespace
from pyperclip import copy, paste
from uvicorn import Config, Server
from typing import Callable

from expansion import (
    # BrowserCookie,
    Cleaner,
    Converter,
    Namespace,
    beautify_string,
)
from module import (
    __VERSION__,
    ERROR,
    MASTER,
    REPOSITORY,
    ROOT,
    VERSION_BETA,
    VERSION_MAJOR,
    VERSION_MINOR,
    WARNING,
    DataRecorder,
    ExtractData,
    ExtractParams,
    IDRecorder,
    Manager,
    MapRecorder,
    logging,
    # sleep_time,
    ScriptServer,
    INFO,
)
from translation import _, switch_language

from module import Mapping
from application.download import Download
from application.explore import Explore
from application.image import Image
from application.request import Html
from application.video import Video
from rich import print

__all__ = ["XHS"]


def data_cache(function):
    async def inner(
        self,
        data: dict,
    ):
        if self.manager.record_data:
            download = data["下载地址"]
            lives = data["动图地址"]
            await function(
                self,
                data,
            )
            data["下载地址"] = download
            data["动图地址"] = lives

    return inner


class Print:
    def __init__(
        self,
        func: Callable = print,
    ):
        self.func = func

    def __call__(
        self,
    ):
        return self.func


class XHS:
    VERSION_MAJOR = VERSION_MAJOR
    VERSION_MINOR = VERSION_MINOR
    VERSION_BETA = VERSION_BETA
    LINK = compile(r"(?:https?://)?www\.xiaohongshu\.com/explore/\S+")
    USER = compile(r"(?:https?://)?www\.xiaohongshu\.com/user/profile/[a-z0-9]+/\S+")
    SHARE = compile(r"(?:https?://)?www\.xiaohongshu\.com/discovery/item/\S+")
    SHORT = compile(r"(?:https?://)?xhslink\.com/[^\s\"<>\\^`{|}，。；！？、【】《》]+")
    ID = compile(r"(?:explore|item)/(\S+)?\?")
    ID_USER = compile(r"user/profile/[a-z0-9]+/(\S+)?\?")
    __INSTANCE = None
    CLEANER = Cleaner()

    def __new__(cls, *args, **kwargs):
        if not cls.__INSTANCE:
            cls.__INSTANCE = super().__new__(cls)
        return cls.__INSTANCE

    def __init__(
        self,
        mapping_data: dict = None,
        work_path="",
        folder_name="Download",
        name_format="发布时间 作者昵称 作品标题",
        user_agent: str = None,
        cookie: str = "",
        proxy: str | dict = None,
        timeout=10,
        chunk=1024 * 1024,
        max_retry=5,
        record_data=False,
        image_format="JPEG",
        image_download=True,
        video_download=True,
        live_download=False,
        video_preference="resolution",
        folder_mode=False,
        download_record=True,
        author_archive=False,
        write_mtime=False,
        language="zh_CN",
        # read_cookie: int | str = None,
        script_server: bool = False,
        script_host="0.0.0.0",
        script_port=5558,
        **kwargs,
    ):
        switch_language(language)
        self.print = Print()
        self.manager = Manager(
            ROOT,
            work_path,
            folder_name,
            name_format,
            chunk,
            user_agent,
            cookie,
            # self.read_browser_cookie(read_cookie) or cookie,
            proxy,
            timeout,
            max_retry,
            record_data,
            image_format,
            image_download,
            video_download,
            live_download,
            video_preference,
            download_record,
            folder_mode,
            author_archive,
            write_mtime,
            script_server,
            self.CLEANER,
            self.print,
        )
        self.mapping_data = mapping_data or {}
        self.map_recorder = MapRecorder(
            self.manager,
        )
        self.mapping = Mapping(self.manager, self.map_recorder)
        self.html = Html(self.manager)
        self.image = Image()
        self.video = Video()
        self.explore = Explore()
        self.convert = Converter()
        self.download = Download(self.manager)
        self.id_recorder = IDRecorder(self.manager)
        self.data_recorder = DataRecorder(self.manager)
        self.clipboard_cache: str = ""
        self.queue = Queue()
        self.event = Event()
        self.script = None
        self.init_script_server(
            script_host,
            script_port,
        )
        self.semaphore = Semaphore(2)  # 限制并发下载数，提升稳定性
        self.progress_tasks = {} # 进度追踪
        self.ext_tools = {
            "all_in_one": {
                "name": "XHS_ALL_IN_ONE",
                "path": "/Users/cc/XHS_ALL_IN_ONE",
                "process": None,
                "port": 5173
            }
        }

    def __extract_image(self, container: dict, data: Namespace):
        container["下载地址"], container["动图地址"] = self.image.get_image_link(
            data, self.manager.image_format
        )

    def __extract_video(
        self,
        container: dict,
        data: Namespace,
    ):
        container["下载地址"] = self.video.deal_video_link(
            data,
            self.manager.video_preference,
        )
        container["动图地址"] = [
            None,
        ]

    async def _get_all_in_one_token(self):
        # 自动登录 ALL_IN_ONE 获取 Token
        if hasattr(self, "_aio_token") and self._aio_token:
            return self._aio_token
        
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post("http://localhost:8000/api/auth/login", data={
                    "username": "admin",
                    "password": "password123"
                }, timeout=5.0)
                if resp.status_code == 200:
                    self._aio_token = resp.json().get("access_token")
                    return self._aio_token
        except:
            pass
        return None

    async def _proxy_all_in_one(self, path: str, payload: dict, method: str = "POST"):
        import httpx
        url = f"http://localhost:8000{path}"
        token = await self._get_all_in_one_token()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        
        try:
            async with httpx.AsyncClient() as client:
                if method == "POST":
                    resp = await client.post(url, json=payload, headers=headers, timeout=60.0)
                else:
                    resp = await client.get(url, params=payload, headers=headers, timeout=60.0)
                
                if resp.status_code == 200:
                    return {"success": True, "data": resp.json()}
                else:
                    return {"success": False, "error": f"ALL_IN_ONE 报错 ({resp.status_code}): {resp.text}"}
        except Exception as e:
            return {"success": False, "error": f"无法连接到 ALL_IN_ONE (请确保已启动): {str(e)}"}

    async def __download_files(
        self,
        container: dict,
        download: bool,
        index,
        count: SimpleNamespace,
        task_id: str = None,
    ):
        name = self.__naming_rules(container)
        if (u := container["下载地址"]) and download:
            if await self.skip_download(i := container["作品ID"]):
                self.logging(_("作品 {0} 存在下载记录，跳过下载").format(i))
                count.skip += 1
            else:
                # 进度回调
                async def progress_callback(percent):
                    if task_id:
                        self.progress_tasks[task_id] = percent

                __, result = await self.download.run(
                    u,
                    container["动图地址"],
                    index,
                    container["作者ID"]
                    + "_"
                    + self.CLEANER.filter_name(container["作者昵称"]),
                    name,
                    container["作品类型"],
                    container["时间戳"],
                    progress_callback,
                )
                if not result:
                    count.skip += 1
                elif all(result):
                    count.success += 1
                    await self.__add_record(
                        i,
                    )
                else:
                    count.fail += 1
        elif not u:
            self.logging(_("提取作品文件下载地址失败"), ERROR)
            count.fail += 1
        await self.save_data(container)

    @data_cache
    async def save_data(
        self,
        data: dict,
    ):
        data["采集时间"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data["下载地址"] = " ".join(data["下载地址"])
        data["动图地址"] = " ".join(i or "NaN" for i in data["动图地址"])
        data.pop("时间戳", None)
        await self.data_recorder.add(**data)

    async def __add_record(
        self,
        id_: str,
    ) -> None:
        await self.id_recorder.add(id_)

    async def extract(
        self,
        url: str,
        download=False,
        index: list | tuple = None,
        data=True,
    ) -> list[dict]:
        if not (
            urls := await self.extract_links(
                url,
            )
        ):
            self.logging(_("提取小红书作品链接失败"), WARNING)
            return []
        statistics = SimpleNamespace(
            all=len(urls),
            success=0,
            fail=0,
            skip=0,
        )
        self.logging(_("共 {0} 个小红书作品待处理...").format(statistics.all))
        result = [
            await self._deal_extract(
                i,
                download,
                index,
                data,
                count=statistics,
            )
            for i in urls
        ]
        self.show_statistics(
            statistics,
        )
        return result

    def show_statistics(
        self,
        statistics: SimpleNamespace,
    ) -> None:
        self.logging(
            _("共处理 {0} 个作品，成功 {1} 个，失败 {2} 个，跳过 {3} 个").format(
                statistics.all,
                statistics.success,
                statistics.fail,
                statistics.skip,
            ),
        )

    async def extract_cli(
        self,
        url: str,
        download=True,
        index: list | tuple = None,
        data=False,
    ) -> None:
        url = await self.extract_links(
            url,
        )
        if not url:
            self.logging(_("提取小红书作品链接失败"), WARNING)
            return
        if index:
            await self._deal_extract(
                url[0],
                download,
                index,
                data,
            )
        else:
            statistics = SimpleNamespace(
                all=len(url),
                success=0,
                fail=0,
                skip=0,
            )
            [
                await self._deal_extract(
                    u,
                    download,
                    index,
                    data,
                    count=statistics,
                )
                for u in url
            ]
            self.show_statistics(
                statistics,
            )

    async def extract_links(
        self,
        url: str,
    ) -> list:
        urls = []
        for i in url.split():
            if u := self.SHORT.search(i):
                i = await self.html.request_url(
                    u.group(),
                    False,
                )
            if u := self.SHARE.search(i):
                urls.append(u.group())
            elif u := self.LINK.search(i):
                urls.append(u.group())
            elif u := self.USER.search(i):
                urls.append(u.group())
        return urls

    def extract_id(self, links: list[str]) -> list[str]:
        ids = []
        for i in links:
            if j := self.ID.search(i):
                ids.append(j.group(1))
            elif j := self.ID_USER.search(i):
                ids.append(j.group(1))
        return ids

    async def _get_html_data(
        self,
        url: str,
        data: bool,
        cookie: str = None,
        proxy: str = None,
        count=SimpleNamespace(
            all=0,
            success=0,
            fail=0,
            skip=0,
        ),
    ) -> tuple[str, Namespace | dict]:
        if await self.skip_download(id_ := self.__extract_link_id(url)) and not data:
            msg = _("作品 {0} 存在下载记录，跳过处理").format(id_)
            self.logging(msg)
            count.skip += 1
            return id_, {"message": msg}
        self.logging(_("开始处理作品：{0}").format(id_))
        html = await self.html.request_url(
            url,
            cookie=cookie,
            proxy=proxy,
        )
        namespace = self.__generate_data_object(html)
        if not namespace:
            self.logging(_("{0} 获取数据失败").format(id_), ERROR)
            count.fail += 1
            return id_, {}
        return id_, namespace

    def _extract_data(
        self,
        namespace: Namespace,
        id_: str,
        count,
    ):
        data = self.explore.run(namespace)
        if not data:
            self.logging(_("{0} 提取数据失败").format(id_), ERROR)
            count.fail += 1
            return {}
        return data

    async def _deal_download_tasks(
        self,
        data: dict,
        namespace: Namespace,
        id_: str,
        download: bool,
        index: list | tuple | None,
        count: SimpleNamespace,
        task_id: str = None,
    ):
        if data["作品类型"] == _("视频"):
            self.__extract_video(data, namespace)
        elif data["作品类型"] in {
            _("图文"),
            _("图集"),
        }:
            self.__extract_image(data, namespace)
        else:
            self.logging(_("未知的作品类型：{0}").format(id_), WARNING)
            data["下载地址"] = []
            data["动图地址"] = []
        await self.update_author_nickname(
            data,
        )
        await self.__download_files(
            data,
            download,
            index,
            count,
            task_id,
        )
        # await sleep_time()
        return data
    async def _deal_extract(
        self,
        url: str,
        download: bool,
        index: list | tuple | None,
        data: bool,
        cookie: str = None,
        proxy: str = None,
        work_path: str = None,
        count=SimpleNamespace(
            all=0,
            success=0,
            fail=0,
            skip=0,
        ),
        task_id: str = None,
    ):
        # 如果提供了自定义路径，临时应用它
        old_path = self.manager.work_path
        if work_path:
            self.manager.work_path = Path(work_path)
            self.manager.folder = self.manager.work_path.joinpath(self.manager.folder_name)

        try:
            id_, namespace = await self._get_html_data(
                url,
                data,
                cookie,
                proxy,
                count,
            )
            if not isinstance(namespace, Namespace):
                return namespace
            if not (
                data := self._extract_data(
                    namespace,
                    id_,
                    count,
                )
            ):
                return data
            data = await self._deal_download_tasks(
                data
                | {
                    "作品链接": url,
                },
                namespace,
                id_,
                download,
                index,
                count,
                task_id,
            )
            self.logging(_("作品处理完成：{0}").format(id_))
            return data
        finally:
            # 还原路径
            if work_path:
                self.manager.work_path = old_path
                self.manager.folder = self.manager.work_path.joinpath(self.manager.folder_name)

    async def deal_script_tasks(
        self,
        data: dict,
        index: list | tuple | None,
        count=SimpleNamespace(
            all=0,
            success=0,
            fail=0,
            skip=0,
        ),
    ):
        namespace = self.json_to_namespace(data)
        id_ = namespace.safe_extract("noteId", "")
        if not (
            data := self._extract_data(
                namespace,
                id_,
                count,
            )
        ):
            return data
        return await self._deal_download_tasks(
            data,
            namespace,
            id_,
            True,
            index,
            count,
        )

    @staticmethod
    def json_to_namespace(data: dict) -> Namespace:
        return Namespace(data)

    async def update_author_nickname(
        self,
        container: dict,
    ):
        if a := self.CLEANER.filter_name(
            self.mapping_data.get(i := container["作者ID"], "")
        ):
            container["作者昵称"] = a
        else:
            container["作者昵称"] = self.manager.filter_name(container["作者昵称"]) or i
        await self.mapping.update_cache(
            i,
            container["作者昵称"],
        )

    @staticmethod
    def __extract_link_id(url: str) -> str:
        link = urlparse(url)
        return link.path.split("/")[-1]

    def __generate_data_object(self, html: str) -> Namespace:
        data = self.convert.run(html)
        return Namespace(data)

    def __naming_rules(self, data: dict) -> str:
        keys = self.manager.name_format.split()
        values = []
        for key in keys:
            match key:
                case "发布时间":
                    values.append(self.__get_name_time(data))
                case "作品标题":
                    values.append(self.__get_name_title(data))
                case _:
                    values.append(data[key])
        return beautify_string(
            self.CLEANER.filter_name(
                self.manager.SEPARATE.join(values),
                default=self.manager.SEPARATE.join(
                    (
                        data["作者ID"],
                        data["作品ID"],
                    )
                ),
            ),
            length=128,
        )

    @staticmethod
    def __get_name_time(data: dict) -> str:
        return data["发布时间"].replace(":", ".")

    def __get_name_title(self, data: dict) -> str:
        return (
            beautify_string(
                self.manager.filter_name(data["作品标题"]),
                64,
            )
            or data["作品ID"]
        )

    async def monitor(
        self,
        delay=1,
        download=True,
        data=False,
    ) -> None:
        self.logging(
            _(
                "程序会自动读取并提取剪贴板中的小红书作品链接，并自动下载链接对应的作品文件，如需关闭，请点击关闭按钮，或者向剪贴板写入 “close” 文本！"
            ),
            style=MASTER,
        )
        self.event.clear()
        copy("")
        await gather(
            self.__get_link(delay),
            self.__receive_link(delay, download=download, index=None, data=data),
        )

    async def __get_link(self, delay: int):
        while not self.event.is_set():
            if (t := paste()).lower() == "close":
                self.stop_monitor()
            elif t != self.clipboard_cache:
                self.clipboard_cache = t
                create_task(self.__push_link(t))
            await sleep(delay)

    async def __push_link(
        self,
        content: str,
    ):
        await gather(
            *[
                self.queue.put(i)
                for i in await self.extract_links(
                    content,
                )
            ]
        )

    async def __receive_link(self, delay: int, *args, **kwargs):
        while not self.event.is_set() or self.queue.qsize() > 0:
            with suppress(QueueEmpty):
                await self._deal_extract(self.queue.get_nowait(), *args, **kwargs)
            await sleep(delay)

    def stop_monitor(self):
        self.event.set()

    async def skip_download(self, id_: str) -> bool:
        return bool(await self.id_recorder.select(id_))

    async def __aenter__(self):
        await self.id_recorder.__aenter__()
        await self.data_recorder.__aenter__()
        await self.map_recorder.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.id_recorder.__aexit__(exc_type, exc_value, traceback)
        await self.data_recorder.__aexit__(exc_type, exc_value, traceback)
        await self.map_recorder.__aexit__(exc_type, exc_value, traceback)
        await self.close()

    async def close(self):
        await self.stop_script_server()
        await self.manager.close()

    # @staticmethod
    # def read_browser_cookie(value: str | int) -> str:
    #     return (
    #         BrowserCookie.get(
    #             value,
    #             domains=[
    #                 "xiaohongshu.com",
    #             ],
    #         )
    #         if value
    #         else ""
    #     )

    async def run_api_server(
        self,
        host="0.0.0.0",
        port=5556,
        log_level="info",
    ):
        api = FastAPI(
            debug=self.VERSION_BETA,
            title="XHS-Downloader",
            version=__VERSION__,
        )
        self.setup_routes(api)
        config = Config(
            api,
            host=host,
            port=port,
            log_level=log_level,
        )
        server = Server(config)
        await server.serve()

    def setup_routes(
        self,
        server: FastAPI,
    ):
        # 挂载静态文件
        frontend_path = ROOT.parent.joinpath("frontend")
        if frontend_path.exists():
            server.mount("/ui", StaticFiles(directory=str(frontend_path)), name="ui")

        @server.get(
            "/",
            summary=_("控制台界面"),
            description=_("访问 XHS-Downloader Web 控制台"),
            tags=["UI"],
        )
        async def index():
            index_file = frontend_path.joinpath("index.html")
            if index_file.exists():
                return FileResponse(index_file)
            return RedirectResponse(url=REPOSITORY)

        @server.get("/style.css", include_in_schema=False)
        async def get_css():
            return FileResponse(frontend_path.joinpath("style.css"))

        @server.get("/app.js", include_in_schema=False)
        async def get_js():
            return FileResponse(frontend_path.joinpath("app.js"))

        @server.get("/xhs/check_update", tags=["System"])
        async def check_update():
            try:
                # 尝试检查 git 更新
                subprocess.run(["git", "fetch"], cwd=str(ROOT.parent), capture_output=True, timeout=5)
                status = subprocess.run(["git", "status", "-uno"], cwd=str(ROOT.parent), capture_output=True, text=True, timeout=5)
                if "Your branch is behind" in status.stdout:
                    return {"need_update": True, "latest_version": "GitHub 最新版"}
                return {"need_update": False, "current_version": __VERSION__}
            except Exception as e:
                return {"need_update": False, "error": str(e)}

        @server.post("/xhs/do_update", tags=["System"])
        async def do_update():
            try:
                # 执行 git pull
                process = subprocess.run(["git", "pull"], cwd=str(ROOT.parent), capture_output=True, text=True, timeout=30)
                if process.returncode == 0:
                    return {"success": True}
                return {"success": False, "error": process.stderr}
            except Exception as e:
                return {"success": False, "error": str(e)}

        @server.get("/xhs/tasks", tags=["System"])
        async def get_tasks():
            return self.progress_tasks

        @server.get("/xhs/tools/status", tags=["Tools"])
        async def get_tools_status():
            status = {}
            for k, v in self.ext_tools.items():
                # 检查端口是否占用
                proc = subprocess.run(["lsof", "-i", f":{v['port']}", "-t"], capture_output=True, text=True)
                is_running = bool(proc.stdout.strip())
                status[k] = {"name": v["name"], "running": is_running, "url": f"http://localhost:{v['port']}"}
            return status

        @server.post("/xhs/tools/start/{tool_id}", tags=["Tools"])
        async def start_tool(tool_id: str):
            if tool_id not in self.ext_tools:
                return {"success": False, "error": "未知工具"}
            
            tool = self.ext_tools[tool_id]
            # 异步启动脚本
            try:
                subprocess.Popen(["bash", "./start.sh"], cwd=tool["path"], start_new_session=True)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        @server.post("/xhs/ext/save", tags=["Deep Integration"])
        async def ext_save_note(note_data: dict):
            # 将 xhs_tool 的数据格式转换为 XHS_ALL_IN_ONE 的格式
            payload = {
                "account_id": 1, 
                "fetch_comments": False,
                "notes": [{
                    "note_id": note_data.get("作品ID"),
                    "note_url": note_data.get("作品链接"),
                    "title": note_data.get("作品标题"),
                    "content": note_data.get("作品描述"),
                    "author_name": note_data.get("作者昵称"),
                    "cover_url": note_data.get("封面地址"),
                    "video_url": note_data.get("下载地址")[0] if note_data.get("作品类型") == "视频" else "",
                    "image_urls": note_data.get("下载地址") if note_data.get("作品类型") != "视频" else [],
                    "raw": note_data
                }]
            }
            return await self._proxy_all_in_one("/api/notes/batch-save", payload)

        @server.post("/xhs/search", tags=["Discovery"])
        async def search_notes(params: dict):
            # 代理到 ALL_IN_ONE 的搜索接口
            payload = {
                "account_id": 1,
                "keyword": params.get("keyword"),
                "page": params.get("page", 1),
                "save_to_library": false
            }
            # ALL_IN_ONE 的搜索接口路径是 /api/xhs/crawl/search-notes
            resp = await self._proxy_all_in_one("/api/xhs/crawl/search-notes", payload)
            if resp.get("success"):
                # 将 ALL_IN_ONE 的格式转换为前端卡片需要的格式
                # 在 search-notes 中，raw 包含 {"data": {"items": [...]}}
                raw_items = resp.get("data", {}).get("raw", {}).get("data", {}).get("items", [])
                normalized = []
                from application.explore import Explore
                from expansion import Namespace
                explorer = Explore()
                for item in raw_items:
                    # 模拟 Explore.run 的输出
                    ns = Namespace(item.get("note_card", item))
                    data = explorer.run(ns)
                    if data:
                        normalized.append(data)
                return {"success": True, "data": {"items": normalized}}
            return resp

        @server.get("/xhs/user/notes", tags=["Discovery"])
        async def get_user_notes(url: str):
            # 获取博主主页的所有作品链接
            payload = {
                "account_id": 1,
                "user_url": url,
                "save_to_library": False
            }
            # ALL_IN_ONE 的用户笔记接口路径是 /api/xhs/crawl/user-notes
            resp = await self._proxy_all_in_one("/api/xhs/crawl/user-notes", payload)
            if resp.get("success"):
                # 在 user-notes 中，raw 是直接的 note_list
                raw_items = resp.get("data", {}).get("raw", [])
                normalized = []
                from application.explore import Explore
                from expansion import Namespace
                explorer = Explore()
                for item in raw_items:
                    ns = Namespace(item)
                    data = explorer.run(ns)
                    if data:
                        normalized.append(data)
                return {"success": True, "data": {"items": normalized}}
            return resp

        @server.post("/xhs/ext/sync_cookie", tags=["Deep Integration"])
        async def sync_cookie_to_ext(payload: dict):
            cookie = payload.get("cookie")
            if not cookie:
                return {"success": False, "error": "Cookie 不能为空"}
            
            # 1. 设置 ALL_IN_ONE 的账号
            aio_payload = {
                "platform": "xhs",
                "sub_type": "pc",
                "cookie_string": cookie,
                "sync_creator": True
            }
            return await self._proxy_all_in_one("/api/accounts/import-cookie", aio_payload)

        @server.get("/xhs/login", tags=["System"])
        async def browser_login():
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto("https://www.xiaohongshu.com")
                
                # 等待用户手动登录完成 (通过检查某个只有登录后才有的元素，或者简单的等待)
                print("等待用户在浏览器中完成登录...")
                try:
                    # 等待 'header-container' 或其他登录后的特征
                    await page.wait_for_selector(".user-info", timeout=300000) # 5分钟超时
                    cookies = await context.cookies()
                    cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
                    await browser.close()
                    return {"success": True, "cookie": cookie_str}
                except Exception as e:
                    await browser.close()
                    return {"success": False, "error": "登录超时或被关闭"}

        @server.post(
            "/xhs/detail",
            summary=_("获取作品数据及下载地址"),
            description=_(
                dedent("""
                **参数**:
                        
                - **url**: 小红书作品链接，自动提取，不支持多链接；必需参数
                - **download**: 是否下载作品文件；设置为 true 将会耗费更多时间；可选参数
                - **index**: 下载指定序号的图片文件，仅对图文作品生效；download 参数设置为 false 时不生效；可选参数
                - **cookie**: 请求数据时使用的 Cookie；可选参数
                - **proxy**: 请求数据时使用的代理；可选参数
                - **skip**: 是否跳过存在下载记录的作品；设置为 true 将不会返回存在下载记录的作品数据；可选参数
                """)
            ),
            tags=["API"],
            response_model=ExtractData,
        )
        async def handle(extract: ExtractParams):
            async with self.semaphore:  # 使用信号量限制并发
                data = None
                url = await self.extract_links(
                    extract.url,
                )
                if not url:
                    msg = _("提取小红书作品链接失败")
                else:
                    try:
                        if data := await self._deal_extract(
                            url[0],
                            extract.download,
                            extract.index,
                            not extract.skip,
                            extract.cookie,
                            extract.proxy,
                            extract.work_path,
                            task_id=extract.task_id, # 传入任务ID
                        ):
                            msg = _("获取小红书作品数据成功")
                        else:
                            msg = _("获取小红书作品数据失败")
                    except Exception as e:
                        msg = f"发生意外错误: {str(e)}"
                return ExtractData(message=msg, params=extract, data=data)

    async def run_mcp_server(
        self,
        transport="streamable-http",
        host="0.0.0.0",
        port=5556,
        log_level="INFO",
    ):
        mcp = FastMCP(
            "XHS-Downloader",
            instructions=dedent("""
                本服务器提供两个 MCP 接口，分别用于获取小红书作品信息数据和下载小红书作品文件，二者互不依赖，可独立调用。
                
                支持的作品链接格式：
                - https://www.xiaohongshu.com/explore/...
                - https://www.xiaohongshu.com/discovery/item/...
                - https://xhslink.com/...
                
                get_detail_data
                功能：输入小红书作品链接，返回该作品的信息数据，不会下载文件。
                参数：
                - url（必填）：小红书作品链接
                返回：
                - message：结果提示
                - data：作品信息数据
                
                download_detail
                功能：输入小红书作品链接，下载作品文件，默认不返回作品信息数据。
                参数：
                - url（必填）：小红书作品链接
                - index（选填）：根据用户指定的图片序号（如用户说“下载第1和第3张”时，index应为 [1, 3]），生成由所需图片序号组成的列表；如果用户未指定序号，则该字段为 None
                - return_data（可选）：是否返回作品信息数据；如需返回作品信息数据，设置此参数为 true，默认值为 false
                返回：
                - message：结果提示
                - data：作品信息数据，不需要返回作品信息数据时固定为 None
                """),
            version=__VERSION__,
        )

        @mcp.tool(
            name="get_detail_data",
            description=dedent("""
                功能：输入小红书作品链接，返回该作品的信息数据，不会下载文件。
                
                参数：
                url（必填）：小红书作品链接，格式如：
                - https://www.xiaohongshu.com/explore/...
                - https://www.xiaohongshu.com/discovery/item/...
                - https://xhslink.com/...
                
                返回：
                - message：结果提示
                - data：作品信息数据
                """),
            tags={
                "小红书",
                "XiaoHongShu",
                "RedNote",
            },
            annotations={
                "title": "获取小红书作品信息数据",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            },
        )
        async def get_detail_data(
            url: Annotated[str, Field(description=_("小红书作品链接"))],
        ) -> dict:
            msg, data = await self.deal_detail_mcp(
                url,
                False,
                None,
            )
            return {
                "message": msg,
                "data": data,
            }

        @mcp.tool(
            name="download_detail",
            description=dedent("""
                功能：输入小红书作品链接，下载作品文件，默认不返回作品信息数据。
                
                参数：
                url（必填）：小红书作品链接，格式如：
                - https://www.xiaohongshu.com/explore/...
                - https://www.xiaohongshu.com/discovery/item/...
                - https://xhslink.com/...
                index（选填）：根据用户指定的图片序号（如用户说“下载第1和第3张”时，index应为 [1, 3]），生成由所需图片序号组成的列表；如果用户未指定序号，则该字段为 None
                return_data（可选）：是否返回作品信息数据；如需返回作品信息数据，设置此参数为 true，默认值为 false
                
                返回：
                - message：结果提示
                - data：作品信息数据，不需要返回作品信息数据时固定为 None
                """),
            tags={
                "小红书",
                "XiaoHongShu",
                "RedNote",
                "Download",
                "下载",
            },
            annotations={
                "title": "下载小红书作品文件，可以返回作品信息数据",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": True,
            },
        )
        async def download_detail(
            url: Annotated[str, Field(description=_("小红书作品链接"))],
            index: Annotated[
                list[str | int] | None,
                Field(default=None, description=_("指定需要下载的图文作品序号")),
            ],
            return_data: Annotated[
                bool,
                Field(default=False, description=_("是否需要返回作品信息数据")),
            ],
        ) -> dict:
            msg, data = await self.deal_detail_mcp(
                url,
                True,
                index,
            )
            match (
                bool(data),
                return_data,
            ):
                case (True, True):
                    return {
                        "message": msg + ", " + _("作品文件下载任务执行完毕"),
                        "data": data,
                    }
                case (True, False):
                    return {
                        "message": _("作品文件下载任务执行完毕"),
                        "data": None,
                    }
                case (False, True):
                    return {
                        "message": msg + ", " + _("作品文件下载任务未执行"),
                        "data": None,
                    }
                case (False, False):
                    return {
                        "message": msg + ", " + _("作品文件下载任务未执行"),
                        "data": None,
                    }
                case _:
                    raise ValueError

        await mcp.run_async(
            transport=transport,
            host=host,
            port=port,
            log_level=log_level,
        )

    async def deal_detail_mcp(
        self,
        url: str,
        download: bool,
        index: list[str | int] | None,
    ):
        data = None
        url = await self.extract_links(
            url,
        )
        if not url:
            msg = _("提取小红书作品链接失败")
        elif data := await self._deal_extract(
            url[0],
            download,
            index,
            True,
        ):
            msg = _("获取小红书作品数据成功")
        else:
            msg = _("获取小红书作品数据失败")
        return msg, data

    def init_script_server(
        self,
        host="0.0.0.0",
        port=5558,
    ):
        if self.manager.script_server:
            self.run_script_server(host, port)

    async def switch_script_server(
        self,
        host="0.0.0.0",
        port=5558,
        switch: bool = None,
    ):
        if switch is None:
            switch = self.manager.script_server
        if switch:
            self.run_script_server(
                host,
                port,
            )
        else:
            await self.stop_script_server()

    def run_script_server(
        self,
        host="0.0.0.0",
        port=5558,
    ):
        if not self.script:
            self.script = create_task(self._run_script_server(host, port))

    async def _run_script_server(
        self,
        host="0.0.0.0",
        port=5558,
    ):
        async with ScriptServer(self, host, port):
            await Future()

    async def stop_script_server(self):
        if self.script:
            self.script.cancel()
            with suppress(CancelledError):
                await self.script
            self.script = None

    async def _script_server_debug(self):
        await self.switch_script_server(
            switch=self.manager.script_server,
        )

    def logging(self, text, style=INFO):
        logging(
            self.print,
            text,
            style,
        )
