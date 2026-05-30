import {
  CheckOutlined,
  CloudDownloadOutlined,
  CommentOutlined,
  DatabaseOutlined,
  FolderOpenOutlined,
  GlobalOutlined,
  HeartOutlined,
  LeftOutlined,
  LinkOutlined,
  LoadingOutlined,
  PictureOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  RocketOutlined,
  RightOutlined,
  SearchOutlined,
  StarOutlined,
} from "@ant-design/icons";
import { Alert, Button, Card, Col, Empty, Input, Progress, Row, Select, Space, Tag, Typography, message } from "antd";
import { useEffect, useMemo, useState } from "react";

import { apiUrl, downloadXhsNote, fetchAccounts, fetchSavedNoteIds, fetchXhsUserNotes, http, saveXhsNotesToLibrary } from "../../../lib/api";
import type { PlatformAccount, XhsSearchNote } from "../../../types";

const { Title, Text } = Typography;

function formatMetric(value: number): string {
  if (value >= 10000) return `${(value / 10000).toFixed(value >= 100000 ? 0 : 1)}w`;
  return value?.toLocaleString() || "0";
}

export function XhsFastDownloadPage() {
  const [accounts, setAccounts] = useState<PlatformAccount[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [urlInput, setUrlInput] = useState("");
  const [bloggerUrl, setBloggerUrl] = useState("");
  const [isCrawlingBlogger, setIsCrawlingBlogger] = useState(false);
  const [tasks, setTasks] = useState<Array<Record<string, any>>>([]);
  const [isLoadingAccounts, setIsLoadingAccounts] = useState(true);
  const [savedNoteIds, setSavedNoteIds] = useState<string[]>([]);
  const [progressMap, setProgressMap] = useState<Record<string, number>>({});

  const pcAccounts = useMemo(() => accounts.filter((a) => a.platform === "xhs" && a.sub_type === "pc"), [accounts]);
  const pcAccountOptions = useMemo(() => pcAccounts.map((a) => ({ value: a.id, label: `${a.nickname || `PC ${a.id}`} · ${a.status}` })), [pcAccounts]);

  async function loadAccounts() {
    setIsLoadingAccounts(true);
    try {
      const loaded = await fetchAccounts("xhs");
      setAccounts(loaded);
      const first = loaded.find((a) => a.sub_type === "pc");
      setSelectedAccountId((c) => c ?? first?.id ?? null);
    } catch {
      message.error("账号列表加载失败");
    } finally {
      setIsLoadingAccounts(false);
    }
  }

  async function loadSavedNoteIds() {
    try {
      const ids = await fetchSavedNoteIds("xhs");
      setSavedNoteIds(ids);
    } catch { /* ignore */ }
  }

  useEffect(() => {
    void loadAccounts();
    void loadSavedNoteIds();

    // 进度轮询
    const timer = setInterval(async () => {
      try {
        const res = await http.get("/fast-downloader/tasks", { _silent: true } as never);
        setProgressMap(res.data);
      } catch { /* silent */ }
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  async function handleBloggerCrawl() {
    if (!selectedAccountId) { message.warning("请先选择一个账号"); return; }
    const cleanUrl = bloggerUrl.trim();
    if (!cleanUrl || !cleanUrl.includes("/user/profile/")) { message.warning("请输入有效的博主主页链接"); return; }
    
    setIsCrawlingBlogger(true);
    try {
      const response = await fetchXhsUserNotes({ account_id: selectedAccountId, user_url: cleanUrl });
      if (response.items && response.items.length > 0) {
        message.success(`成功获取 ${response.items.length} 篇笔记，已加入队列`);
        for (const note of response.items) {
          const taskId = "task_" + Math.random().toString(36).substr(2, 9);
          // 将 XhsSearchNote 格式转换为下载任务格式
          const downloadTask = {
            id: taskId,
            url: note.note_url,
            "作品ID": note.note_id,
            "作品标题": note.title,
            "作者昵称": note.author_name,
            "封面地址": note.cover_url,
            "作品类型": note.type,
            "点赞数量": note.likes,
            "收藏数量": note.collects,
            "评论数量": note.comments,
            status: "pending"
          };
          setTasks((prev) => [downloadTask, ...prev]);
          void processTask(taskId, note.note_url || "");
        }
        setBloggerUrl("");
      } else {
        message.info("该博主主页暂无公开笔记");
      }
    } catch (e) {
      message.error("获取博主笔记失败");
    } finally {
      setIsCrawlingBlogger(false);
    }
  }

  async function handleFastDownload() {
    if (!selectedAccountId) {
      message.warning("请先绑定并选择一个 PC 账号");
      return;
    }
    const urls = urlInput.match(/https?:\/\/[^\s]+/g);
    if (!urls) {
      message.warning("请输入有效的小红书链接");
      return;
    }
    setUrlInput("");

    for (const url of urls) {
      const taskId = "task_" + Math.random().toString(36).substr(2, 9);
      // 添加一个临时任务卡片
      setTasks((prev) => [{ id: taskId, url, status: "pending" }, ...prev]);
      void processTask(taskId, url);
    }
  }

  async function openDownloadFolder() {
    try {
      const res = await http.post("/ops/open-folder", { path: "backend/Volume/Download" });
      const data = res.data as { opened?: boolean; path?: string; message?: string };
      if (data?.opened) {
        message.success(data.message || "已打开下载目录");
      } else {
        message.info(data?.message || data?.path || "已返回下载目录路径");
      }
    } catch {
      // http interceptor already shows message.error
    }
  }

  async function openTaskFolder(task: Record<string, any>) {
    const localDir = task["本地下载目录"];
    const localFiles = Array.isArray(task["本地文件列表"]) ? task["本地文件列表"] : [];
    if (!localDir) {
      message.info("当前任务还没有返回实际下载目录");
      return;
    }
    try {
      const normalized = String(localDir);
      const res = await http.post("/ops/open-folder", { path: normalized, reveal_file: localFiles[0] || null });
      const data = res.data as { opened?: boolean; path?: string; message?: string };
      if (data?.opened) {
        message.success(data.message || "已打开本次下载目录");
      } else {
        await navigator.clipboard.writeText(normalized).catch(() => undefined);
        message.info((data?.message || data?.path || "已返回本次下载目录路径") + "，目录已复制到剪贴板");
      }
    } catch {
      await navigator.clipboard.writeText(String(localDir)).catch(() => undefined);
      message.warning(`自动打开失败，目录已复制到剪贴板：${localDir}`);
    }
  }

  async function processTask(taskId: string, url: string) {
    try {
      const res = await downloadXhsNote({ url, task_id: taskId, account_id: selectedAccountId });
      if (res.data?.["下载成功"] && (res.data?.["本地文件数量"] || 0) > 0) {
        const completedTask = { ...res.data, id: taskId, status: "completed" };
        setTasks((prev) => prev.map(t => t.id === taskId ? { ...t, ...completedTask } : t));
        const assetLabel = res.data["作品类型"] === "视频" ? "视频" : "图片";
        message.success(`${assetLabel}已就绪: ${res.data["作品标题"] || "作品"}`);
        if (res.data["本地下载目录"]) {
          void openTaskFolder(completedTask);
        }
      } else if (res.data) {
        const firstFailure = Array.isArray(res.data?.["下载失败详情"]) ? res.data["下载失败详情"][0] : null;
        const failureReason = firstFailure?.error || firstFailure?.source || "未检测到本地下载文件，请检查账号权限或原链接资源";
        const errorMessage = `下载失败：${failureReason}`;
        setTasks((prev) => prev.map(t => t.id === taskId ? { ...t, ...res.data, status: "failed", error: errorMessage } : t));
        message.error(errorMessage);
      } else {
        setTasks((prev) => prev.map(t => t.id === taskId ? { ...t, status: "failed", error: res.message } : t));
        message.error(`下载失败: ${res.message}`);
      }
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.response?.data?.message || e?.message || "网络请求失败";
      setTasks((prev) => prev.map(t => t.id === taskId ? { ...t, status: "failed", error: detail } : t));
      message.error(`下载失败: ${detail}`);
    }
  }

  async function handleSaveToLibrary(note: any) {
    if (!selectedAccountId) {
      message.warning("请先选择一个 PC 账号");
      return;
    }
    try {
      // 转换格式
      const xhsNote: XhsSearchNote = {
        note_id: note["作品ID"],
        title: note["作品标题"],
        content: note["作品描述"],
        author_id: note["作者ID"],
        author_name: note["作者昵称"],
        author_avatar: "",
        cover_url: note["封面地址"],
        likes: note["点赞数量"] || 0,
        collects: note["收藏数量"] || 0,
        comments: note["评论数量"] || 0,
        shares: 0,
        type: note["作品类型"],
        raw: note
      };
      await saveXhsNotesToLibrary({ account_id: selectedAccountId, notes: [xhsNote] });
      message.success("已保存到内容库");
      setSavedNoteIds((prev) => [...prev, xhsNote.note_id]);
    } catch {
      message.error("保存失败");
    }
  }

  return (
    <div style={{ maxWidth: 1000, margin: "0 auto" }}>
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>🚀 快速下载器</Title>
          <Text type="secondary">粘贴链接即刻开启无水印秒下，支持批量处理</Text>
        </Col>
        <Col>
          <Space>
            <Button icon={<FolderOpenOutlined />} onClick={openDownloadFolder}>打开下载目录</Button>
            <Button icon={<ReloadOutlined />} onClick={loadAccounts} loading={isLoadingAccounts}>刷新账号</Button>
          </Space>
        </Col>
      </Row>

      {pcAccounts.length === 0 ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="当前没有可用的 PC 下载账号"
          description="请先在账号矩阵中绑定并确认一个可用的 PC 账号，再回来使用快速下载。"
        />
      ) : null}

      <Card style={{ marginBottom: 24, background: "#141414" }}>
        <div style={{ marginBottom: 12 }}>
          <Text strong style={{ color: "rgba(255,255,255,0.85)" }}>笔记链接</Text>
        </div>
        <Input.TextArea
          value={urlInput}
          onChange={(e) => setUrlInput(e.target.value)}
          placeholder="请粘贴小红书链接，支持多个链接批量下载..."
          autoSize={{ minRows: 4, maxRows: 6 }}
          style={{ background: "#1f1f1f", border: "1px solid #303030", color: "#fff", marginBottom: 16 }}
        />

        <div style={{ marginBottom: 12 }}>
          <Text strong style={{ color: "rgba(255,255,255,0.85)" }}>博主主页</Text>
        </div>
        <Row gutter={12} style={{ marginBottom: 16 }}>
          <Col flex="auto">
            <Input
              value={bloggerUrl}
              onChange={(e) => setBloggerUrl(e.target.value)}
              placeholder="粘贴博主主页链接，自动下载该博主的所有笔记..."
              style={{ background: "#1f1f1f", border: "1px solid #303030", color: "#fff" }}
            />
          </Col>
          <Col>
            <Button icon={<SearchOutlined />} loading={isCrawlingBlogger} onClick={handleBloggerCrawl}>博主直下</Button>
          </Col>
        </Row>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Space>
            <Text type="secondary" style={{ fontSize: 12 }}>下载账号: </Text>
            <Select
              value={selectedAccountId}
              onChange={setSelectedAccountId}
              size="small"
              style={{ width: 180 }}
              options={pcAccountOptions}
            />
          </Space>
          <Button type="primary" size="large" icon={<RocketOutlined />} onClick={handleFastDownload}>立即开始批量下载</Button>
        </div>
      </Card>

      <div style={{ marginBottom: 16 }}>
        <Title level={5}>下载队列 ({tasks.length})</Title>
      </div>

      <Row gutter={[16, 16]}>
        {tasks.length === 0 ? (
          <Col span={24}>
            <Empty description="暂无下载任务，快去粘贴链接吧" />
          </Col>
        ) : (
          tasks.map((task) => (
            <Col span={24} key={task.id}>
              <Card size="small" style={{ background: "#141414", border: "1px solid #303030" }}>
                <Row gutter={16} align="middle">
                  <Col span={4}>
                    <div style={{ width: "100%", aspectRatio: "3/4", background: "#1f1f1f", borderRadius: 4, overflow: "hidden", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      {task["封面地址"] ? (
                        <img src={task["封面地址"]} alt="封面" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                      ) : (
                        <LoadingOutlined style={{ fontSize: 24, color: "rgba(255,255,255,0.2)" }} />
                      )}
                    </div>
                  </Col>
                  <Col span={20}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                      <Text strong style={{ fontSize: 15, color: "#fff" }}>{task["作品标题"] || (task.status === "pending" ? "正在解析链接..." : "无标题作品")}</Text>
                      <Tag color={task.status === "completed" ? "success" : (task.status === "failed" ? "error" : "processing")}>
                        {task.status === "completed" ? "下载完成" : (task.status === "failed" ? "下载失败" : "正在处理")}
                      </Tag>
                    </div>
                    <div style={{ marginBottom: 12 }}>
                      {task["作者昵称"] && <Text type="secondary" style={{ fontSize: 13 }}>@{task["作者昵称"]} </Text>}
                      {task["作品类型"] && <Tag color="blue">{task["作品类型"]}</Tag>}
                      <div style={{ marginTop: 4 }}>
                        <Space size={12} style={{ fontSize: 12, color: "rgba(255,255,255,0.45)" }}>
                          <span>❤️ {formatMetric(task["点赞数量"])}</span>
                          <span>⭐ {formatMetric(task["收藏数量"])}</span>
                          <span>💬 {formatMetric(task["评论数量"])}</span>
                        </Space>
                      </div>
                    </div>
                    
                    {progressMap[task.id] !== undefined && task.status !== "completed" && (
                      <div style={{ marginBottom: 12 }}>
                        <Progress percent={progressMap[task.id]} size="small" status="active" strokeColor="#ff2442" />
                      </div>
                    )}

                    <Space>
                      <Button size="small" ghost type="primary" icon={<DatabaseOutlined />} disabled={savedNoteIds.includes(task["作品ID"]) || !task["作品ID"]} onClick={() => handleSaveToLibrary(task)}>
                        {savedNoteIds.includes(task["作品ID"]) ? "已存库" : "保存到内容库"}
                      </Button>
                      <Button size="small" icon={<FolderOpenOutlined />} disabled={!task["本地下载目录"]} onClick={() => openTaskFolder(task)}>打开本次目录</Button>
                      <Button size="small" icon={<LinkOutlined />} href={task["作品链接"] || task.url} target="_blank">查看原文</Button>
                      {task.error && <Text type="danger" style={{ fontSize: 12 }}>错误: {task.error}</Text>}
                    </Space>
                    {task["本地下载目录"] ? (
                      <div style={{ marginTop: 8 }}>
                        <Text type="secondary" style={{ fontSize: 12 }}>保存位置：{task["本地下载目录"]}</Text>
                      </div>
                    ) : null}
                  </Col>
                </Row>
              </Card>
            </Col>
          ))
        )}
      </Row>
    </div>
  );
}
