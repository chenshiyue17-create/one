import {
  Alert,
  Avatar,
  Button,
  Card,
  Col,
  Empty,
  Modal,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Switch,
  Tag,
  Typography,
  message,
} from "antd";
import {
  DeleteOutlined,
  PlusOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  SyncOutlined,
  UserOutlined,
  ChromeOutlined,
} from "@ant-design/icons";
import { useEffect, useState } from "react";

import { AddAccountDrawer } from "../../../components/account/add-account-drawer";
import {
  checkAccount,
  deleteAccount,
  fetchAccounts,
  getLocalHelperHealth,
  importXhsCookieFromBrowser,
  pushLocalXhsCookiesToServer,
  readLocalXhsCookies,
  type LocalCookieReadResult,
} from "../../../lib/api";
import { formatShanghaiTime } from "../../../lib/time";
import type { PlatformAccount } from "../../../types";

const { Title, Text } = Typography;

function formatDate(value?: string): string {
  return formatShanghaiTime(value);
}

function profileValue(account: PlatformAccount, key: string): string | null {
  const value = account.profile?.[key];
  if (value === null || value === undefined || value === "") {
    return null;
  }
  return String(value);
}

const statusColorMap: Record<string, string> = {
  active: "green",
  healthy: "green",
  expired: "red",
  unknown: "default",
};

const statusLabelMap: Record<string, string> = {
  active: "正常",
  healthy: "正常",
  expired: "过期",
  unknown: "未知",
};

export function XhsAccountsPage() {
  const [accounts, setAccounts] = useState<PlatformAccount[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [helperStatus, setHelperStatus] = useState<"unknown" | "online" | "offline">("unknown");
  const [helperMessage, setHelperMessage] = useState("尚未检测");
  const [helperBrowser, setHelperBrowser] = useState<"auto" | "chrome" | "edge" | "firefox" | "safari">("auto");
  const [helperSubType, setHelperSubType] = useState<"pc" | "creator">("pc");
  const [helperSyncCreator, setHelperSyncCreator] = useState(true);
  const [cookiePreview, setCookiePreview] = useState<LocalCookieReadResult | null>(null);
  const [isHelperBusy, setIsHelperBusy] = useState(false);
  const [checkingAccountIds, setCheckingAccountIds] = useState<Set<number>>(() => new Set());
  const [error, setError] = useState<string | null>(null);

  async function loadAccounts() {
    setIsLoading(true);
    setError(null);
    try {
      const loadedAccounts = await fetchAccounts("xhs");
      setAccounts(loadedAccounts);
    } catch {
      setError("账号列表加载失败。");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleBrowserSync() {
    setIsSyncing(true);
    try {
      await importXhsCookieFromBrowser({
        sub_type: "pc",
        browser_type: "chrome",
        sync_creator: true
      });
      message.success("已从 Chrome 自动同步账号");
      void loadAccounts();
    } catch (caught: any) {
      const detail = caught?.response?.data?.detail;
      message.error(detail || "未检测到 Chrome 浏览器的小红书登录状态。");
    } finally {
      setIsSyncing(false);
    }
  }

  async function detectLocalHelper() {
    setIsHelperBusy(true);
    try {
      const health = await getLocalHelperHealth();
      setHelperStatus("online");
      setHelperMessage(`${health.service} · ${health.bind}`);
    } catch {
      setHelperStatus("offline");
      setHelperMessage("未检测到本地登录助手，请先运行 ./start-local-helper.sh");
    } finally {
      setIsHelperBusy(false);
    }
  }

  async function handleReadLocalCookie() {
    setIsHelperBusy(true);
    setCookiePreview(null);
    try {
      const preview = await readLocalXhsCookies({ browser_type: helperBrowser });
      setHelperStatus("online");
      setHelperMessage(`读取到 ${preview.cookie_count} 个 Cookie`);
      setCookiePreview(preview);
      message.success("已读取本机浏览器 Cookie，请确认后再同步到服务器。");
    } catch (caught: any) {
      setHelperStatus("offline");
      setHelperMessage(caught?.message || "读取 Cookie 失败");
      message.error(caught?.message || "读取 Cookie 失败");
    } finally {
      setIsHelperBusy(false);
    }
  }

  function handlePushLocalCookie() {
    Modal.confirm({
      title: "确认同步本机登录授权",
      content: "本操作会把当前浏览器的小红书 Cookie 上传到服务器账号库，用于后续抓取/运营任务。不会绕过登录、验证码或风控。",
      okText: "确认同步",
      cancelText: "取消",
      onOk: async () => {
        setIsHelperBusy(true);
        try {
          await pushLocalXhsCookiesToServer({
            browser_type: helperBrowser,
            sub_type: helperSubType,
            sync_creator: helperSubType === "pc" && helperSyncCreator,
          });
          message.success("本地授权已同步到服务器");
          setCookiePreview(null);
          void loadAccounts();
        } catch (caught: any) {
          message.error(caught?.message || "同步失败");
        } finally {
          setIsHelperBusy(false);
        }
      },
    });
  }

  async function handleCheck(accountId: number) {
    if (checkingAccountIds.has(accountId)) {
      return;
    }
    setError(null);
    setCheckingAccountIds((current) => new Set(current).add(accountId));
    try {
      const checked = await checkAccount(accountId);
      setAccounts((current) => current.map((account) => (account.id === checked.id ? checked : account)));
    } catch {
      setError("账号健康检查失败。");
    } finally {
      setCheckingAccountIds((current) => {
        const next = new Set(current);
        next.delete(accountId);
        return next;
      });
    }
  }

  async function handleDelete(account: PlatformAccount) {
    Modal.confirm({
      title: "删除账号",
      content: `删除账号「${account.nickname || account.external_user_id || account.id}」？本地保存的账号 Cookie 也会移除。`,
      okText: "确认删除",
      cancelText: "取消",
      okButtonProps: { danger: true },
      onOk: async () => {
        setError(null);
        try {
          await deleteAccount(account.id);
          setAccounts((current) => current.filter((item) => item.id !== account.id));
        } catch {
          setError("账号删除失败。");
        }
      },
    });
  }

  useEffect(() => {
    async function init() {
      const loadedAccounts = await fetchAccounts("xhs");
      setAccounts(loadedAccounts);
      setIsLoading(false);
    }
    void init();
    void detectLocalHelper();
  }, []);

  return (
    <div style={{ padding: "0 0 32px" }}>
      {/* Page header */}
      <div style={{ marginBottom: 28 }}>
        <Text
          style={{
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: 1.5,
            color: "rgba(255,255,255,0.35)",
            display: "block",
            marginBottom: 4,
          }}
        >
          XHS Accounts
        </Text>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div>
            <Title level={3} style={ { margin: 0, color: "rgba(255,255,255,0.88)" } }>
              账号矩阵
            </Title>
            <Text style={ { color: "rgba(255,255,255,0.45)", marginTop: 4, display: "block" } }>
              管理 PC 与 Creator 账号、Cookie 状态、健康检查和账号作用域。
            </Text>
          </div>
          <Space>
            <Button
              icon={<ChromeOutlined />}
              onClick={handleBrowserSync}
              loading={isSyncing}
              style={ { background: "rgba(22, 119, 255, 0.1)", borderColor: "rgba(22, 119, 255, 0.3)" } }
            >
              一键同步浏览器
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setDrawerOpen(true)}>
              绑定账号
            </Button>
          </Space>
        </div>
      </div>

      <Card
        title={<span style={{ color: "rgba(255,255,255,0.88)", fontWeight: 600 }}>本地登录同步</span>}
        extra={<Tag color={helperStatus === "online" ? "success" : helperStatus === "offline" ? "error" : "default"}>{helperStatus === "online" ? "助手在线" : helperStatus === "offline" ? "助手离线" : "未检测"}</Tag>}
        style={{ background: "#1f1f1f", borderColor: "#303030", marginBottom: 16 }}
        styles={{ body: { padding: 20 } }}
      >
        <Row gutter={[16, 16]} align="middle">
          <Col xs={24} lg={8}>
            <Text strong style={{ display: "block", color: "rgba(255,255,255,0.78)", marginBottom: 4 }}>服务器网页 + 本机登录授权</Text>
            <Text type="secondary">助手只监听 127.0.0.1:8765。读取和上传都需要你点击触发。</Text>
            <div style={{ marginTop: 8 }}>
              <Text type={helperStatus === "offline" ? "danger" : "secondary"}>{helperMessage}</Text>
            </div>
          </Col>
          <Col xs={24} lg={16}>
            <Space wrap>
              <Select
                value={helperBrowser}
                onChange={setHelperBrowser}
                style={{ width: 130 }}
                options={[
                  { value: "auto", label: "自动检测" },
                  { value: "chrome", label: "Chrome" },
                  { value: "edge", label: "Edge" },
                  { value: "firefox", label: "Firefox" },
                  { value: "safari", label: "Safari" },
                ]}
              />
              <Select
                value={helperSubType}
                onChange={setHelperSubType}
                style={{ width: 120 }}
                options={[
                  { value: "pc", label: "PC 账号" },
                  { value: "creator", label: "Creator" },
                ]}
              />
              <Space>
                <Switch checked={helperSyncCreator} onChange={setHelperSyncCreator} disabled={helperSubType !== "pc"} />
                <Text type="secondary">同步 Creator</Text>
              </Space>
              <Button onClick={detectLocalHelper} loading={isHelperBusy}>检测助手</Button>
              <Button onClick={handleReadLocalCookie} loading={isHelperBusy}>读取 Cookie</Button>
              <Button type="primary" onClick={handlePushLocalCookie} loading={isHelperBusy} disabled={!cookiePreview?.has_required}>
                确认同步到服务器
              </Button>
            </Space>
            {cookiePreview ? (
              <Alert
                style={{ marginTop: 12 }}
                type={cookiePreview.has_required ? "success" : "warning"}
                showIcon
                message={`已读取 ${cookiePreview.cookie_count} 个 Cookie`}
                description={`关键 Cookie：${cookiePreview.has_required ? "已检测到" : "未检测到"}；预览：${cookiePreview.cookie_names.slice(0, 8).join(", ")}`}
              />
            ) : null}
          </Col>
        </Row>
      </Card>

      {/* Section card */}
      <Card
        title={
          <span style={{ color: "rgba(255,255,255,0.88)", fontWeight: 600 }}>已绑定账号</span>
        }
        extra={
          <Button icon={<ReloadOutlined />} onClick={loadAccounts} loading={isLoading}>
            刷新
          </Button>
        }
        style={{ background: "#1f1f1f", borderColor: "#303030" }}
        styles={{ body: { padding: 24 } }}
      >
        {error ? <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} /> : null}

        {isLoading ? (
          <div style={{ textAlign: "center", padding: "48px 0" }}>
            <Spin size="large" />
          </div>
        ) : accounts.length === 0 ? (
          <Empty
            image={<SafetyCertificateOutlined style={{ fontSize: 48, color: "rgba(255,255,255,0.25)" }} />}
            imageStyle={{ height: 64 }}
            description={
              <Space direction="vertical" size={4}>
                <Text strong style={{ color: "rgba(255,255,255,0.65)" }}>
                  还没有绑定小红书账号
                </Text>
                <Text style={{ color: "rgba(255,255,255,0.35)", fontSize: 13 }}>
                  先绑定一个 PC 账号，用于搜索、抓取和账号健康检查；Creator 账号用于发布。
                </Text>
              </Space>
            }
          >
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setDrawerOpen(true)}>
              添加账号
            </Button>
          </Empty>
        ) : (
          <Row gutter={[16, 16]}>
            {accounts.map((account) => {
              const isChecking = checkingAccountIds.has(account.id);
              const isCreator = account.sub_type === "creator";
              const statusColor = statusColorMap[account.status] || "default";

              return (
                <Col xs={24} sm={24} md={12} lg={8} key={account.id}>
                  <Card
                    size="small"
                    style={{
                      background: "#1a1a1a",
                      borderColor: isCreator ? "#303050" : "#303030",
                      borderLeft: `3px solid ${isCreator ? "#722ed1" : "#1668dc"}`,
                    }}
                    styles={{ body: { padding: 20 } }}
                  >
                    {/* Head: avatar + name + status */}
                    <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                      <Avatar
                        size={44}
                        src={account.avatar_url || undefined}
                        icon={!account.avatar_url ? <UserOutlined /> : undefined}
                        style={{ background: "#262626", flexShrink: 0 }}
                      >
                        {!account.avatar_url ? (account.nickname?.slice(0, 1).toUpperCase() || "X") : undefined}
                      </Avatar>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <Text
                          strong
                          ellipsis
                          style={{ display: "block", color: "rgba(255,255,255,0.88)", fontSize: 15 }}
                        >
                          {account.nickname || "未命名账号"}
                        </Text>
                        <Text
                          type="secondary"
                          ellipsis
                          style={{ display: "block", fontSize: 12, color: "rgba(255,255,255,0.35)" }}
                        >
                          {account.external_user_id || "external id pending"}
                        </Text>
                      </div>
                      <Tag color={statusColor} style={{ marginRight: 0, flexShrink: 0 }}>
                        {statusLabelMap[account.status] || account.status}
                      </Tag>
                    </div>

                    {/* Stats row */}
                    {isCreator ? (
                      <Row gutter={16} style={{ marginBottom: 12 }}>
                        <Col span={12}>
                          <Statistic
                            title={<span style={{ color: "rgba(255,255,255,0.45)", fontSize: 12 }}>类型</span>}
                            value="Creator"
                            valueStyle={{ color: "rgba(255,255,255,0.88)", fontSize: 14 }}
                          />
                        </Col>
                        {profileValue(account, "red_id") ? (
                          <Col span={12}>
                            <Statistic
                              title={<span style={{ color: "rgba(255,255,255,0.45)", fontSize: 12 }}>小红书号</span>}
                              value={profileValue(account, "red_id") as string}
                              valueStyle={{ color: "rgba(255,255,255,0.88)", fontSize: 14 }}
                            />
                          </Col>
                        ) : null}
                      </Row>
                    ) : (
                      <Row gutter={12} style={{ marginBottom: 12 }}>
                        <Col span={6}>
                          <Statistic
                            title={<span style={{ color: "rgba(255,255,255,0.45)", fontSize: 12 }}>类型</span>}
                            value="PC"
                            valueStyle={{ color: "rgba(255,255,255,0.88)", fontSize: 14 }}
                          />
                        </Col>
                        <Col span={6}>
                          <Statistic
                            title={<span style={{ color: "rgba(255,255,255,0.45)", fontSize: 12 }}>粉丝</span>}
                            value={profileValue(account, "followers") || "-"}
                            valueStyle={{ color: "rgba(255,255,255,0.88)", fontSize: 14 }}
                          />
                        </Col>
                        <Col span={6}>
                          <Statistic
                            title={<span style={{ color: "rgba(255,255,255,0.45)", fontSize: 12 }}>关注</span>}
                            value={profileValue(account, "following") || "-"}
                            valueStyle={{ color: "rgba(255,255,255,0.88)", fontSize: 14 }}
                          />
                        </Col>
                        <Col span={6}>
                          <Statistic
                            title={<span style={{ color: "rgba(255,255,255,0.45)", fontSize: 12 }}>获赞</span>}
                            value={profileValue(account, "likes") || "-"}
                            valueStyle={{ color: "rgba(255,255,255,0.88)", fontSize: 14 }}
                          />
                        </Col>
                      </Row>
                    )}

                    {/* Status message */}
                    {account.status_message ? (
                      <Text
                        type="secondary"
                        style={{ display: "block", fontSize: 12, marginBottom: 12, color: "rgba(255,255,255,0.35)" }}
                      >
                        {account.status_message}
                      </Text>
                    ) : null}

                    {/* Footer: updated time + action buttons */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        paddingTop: 12,
                        borderTop: "1px solid #303030",
                      }}
                    >
                      <Text style={{ fontSize: 11, color: "rgba(255,255,255,0.3)" }}>
                        更新时间：{formatDate(account.updated_at || account.created_at)}
                      </Text>
                      <Space size={4}>
                        <Button
                          size="small"
                          icon={isChecking ? <SyncOutlined spin /> : <ReloadOutlined />}
                          onClick={() => handleCheck(account.id)}
                          disabled={isChecking}
                        >
                          {isChecking ? "检查中" : "检查"}
                        </Button>
                        <Button
                          size="small"
                          danger
                          icon={<DeleteOutlined />}
                          onClick={() => void handleDelete(account)}
                          title="删除账号"
                        />
                      </Space>
                    </div>
                  </Card>
                </Col>
              );
            })}
          </Row>
        )}
      </Card>

      <AddAccountDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} onBound={loadAccounts} />
    </div>
  );
}
