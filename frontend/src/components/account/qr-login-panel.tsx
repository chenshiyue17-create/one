import { Alert, Button, Card, Checkbox, Space, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import axios from "axios";
import { useEffect, useRef, useState } from "react";

import { createXhsCreatorQrLoginSession, createXhsPcQrLoginSession, pollXhsLoginSession } from "../../lib/api";
import type { PlatformAccount, XhsQrLoginSession } from "../../types";

const { Text, Link: AntLink } = Typography;

type QrLoginPanelProps = {
  accountType: "pc" | "creator";
  onConfirmed: (account: PlatformAccount) => void;
  compact?: boolean;
};

export function QrLoginPanel({ accountType, onConfirmed, compact = false }: QrLoginPanelProps) {
  const [session, setSession] = useState<XhsQrLoginSession | null>(null);
  const [statusText, setStatusText] = useState("准备生成二维码");
  const [lastCheckedAt, setLastCheckedAt] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncCreator, setSyncCreator] = useState(false);
  const confirmedRef = useRef(false);

  function errorMessage(error: unknown): string {
    if (axios.isAxiosError(error)) {
      const detail = error.response?.data?.detail;
      if (typeof detail === "string" && detail) {
        return detail;
      }
    }
    return "二维码生成失败，请稍后重试。";
  }

  async function startSession() {
    setIsLoading(true);
    setError(null);
    setLastCheckedAt(null);
    confirmedRef.current = false;
    try {
      const nextSession =
        accountType === "pc"
          ? await createXhsPcQrLoginSession({ sync_creator: syncCreator })
          : await createXhsCreatorQrLoginSession();
      setSession(nextSession);
      setStatusText(
        nextSession.status_message ||
          (accountType === "pc" ? "请使用小红书 App 扫描二维码" : "请使用小红书 App 扫描 Creator 二维码")
      );
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void startSession();
  }, [accountType, syncCreator]);

  useEffect(() => {
    if (!session?.session_id || session.status === "confirmed" || session.status === "expired") {
      return;
    }

    const interval = window.setInterval(async () => {
      try {
        const polled = await pollXhsLoginSession(session.session_id);
        setLastCheckedAt(new Date().toLocaleTimeString());
        setSession((current) => ({
          ...polled,
          qr_image_data_url: polled.qr_image_data_url ?? current?.qr_image_data_url
        }));
        if (polled.status === "scanned") {
          setStatusText(polled.status_message || "已扫码，请在手机端确认登录");
        } else if (polled.status === "expired") {
          setStatusText(polled.status_message || "二维码已过期，请刷新");
        } else if (polled.status === "confirmed" && polled.account && !confirmedRef.current) {
          confirmedRef.current = true;
          setStatusText("账号绑定成功");
          onConfirmed(polled.account);
        } else if (polled.status_message) {
          setStatusText(polled.status_message);
        }
      } catch {
        setError("轮询登录状态失败，正在等待下一次尝试。");
      }
    }, 2000);

    return () => window.clearInterval(interval);
  }, [accountType, onConfirmed, session?.session_id, session?.status]);

  return (
    <Space direction={compact ? "horizontal" : "vertical"} size="middle" style={{ width: "100%", alignItems: compact ? "flex-start" : undefined }}>
      <Card
        styles={{
          body: {
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: compact ? 16 : 24,
            minHeight: compact ? 196 : 220,
            background: "#1f1f1f",
          },
        }}
        style={{ borderColor: "#303030", flexShrink: 0 }}
      >
        {session?.qr_image_data_url ? (
          <img
            src={session.qr_image_data_url}
            alt="小红书登录二维码"
            style={{ width: compact ? 164 : 180, height: compact ? 164 : 180, borderRadius: 8, background: "#fff", padding: 8 }}
          />
        ) : (
          <div
            style={{
              width: compact ? 164 : 180,
              height: compact ? 164 : 180,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "#262626",
              borderRadius: 8,
              color: "rgba(255,255,255,0.3)",
              fontSize: 28,
              fontWeight: 700,
            }}
          >
            QR
          </div>
        )}
      </Card>

      <div style={{ textAlign: compact ? "left" : "center", flex: 1, minWidth: compact ? 260 : undefined }}>
        <Text strong style={{ display: "block", marginBottom: 4, color: "rgba(255,255,255,0.88)" }}>
          {statusText}
        </Text>
        {lastCheckedAt ? (
          <Text type="secondary" style={{ display: "block", marginBottom: 4 }}>
            最后检查：{lastCheckedAt}，状态：{session?.status || "pending"}
          </Text>
        ) : null}
        {session?.qr_url ? (
          <AntLink href={session.qr_url} target="_blank" rel="noreferrer">
            打开二维码链接
          </AntLink>
        ) : null}

        {accountType === "pc" ? (
          <Checkbox
            checked={syncCreator}
            onChange={(event) => setSyncCreator(event.target.checked)}
            style={{ color: "rgba(255,255,255,0.88)", marginTop: 12 }}
          >
            登录 PC 后同步 Creator 账号
          </Checkbox>
        ) : null}

        {error ? <Alert type="error" message={error} showIcon style={{ marginTop: 12 }} /> : null}

        <Button
          block={!compact}
          icon={<ReloadOutlined />}
          onClick={startSession}
          loading={isLoading}
          style={{ marginTop: 12 }}
        >
          {isLoading ? "生成中..." : "刷新二维码"}
        </Button>
      </div>
    </Space>
  );
}
