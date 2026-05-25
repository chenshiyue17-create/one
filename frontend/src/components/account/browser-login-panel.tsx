import { Alert, Button, Card, Input, Space, Typography, message } from "antd";
import { ReloadOutlined, ScanOutlined } from "@ant-design/icons";
import axios from "axios";
import { useEffect, useRef, useState } from "react";

import { http } from "../../lib/api";
import type { PlatformAccount } from "../../types";

const { Text, Title } = Typography;

type BrowserLoginPanelProps = {
  onConfirmed: (account: PlatformAccount) => void;
};

type SessionState = {
  session_id: string;
  state: string;
  status_text: string;
  has_qr: boolean;
  qr_image_b64?: string | null;
  has_captcha: boolean;
  captcha_image_b64?: string | null;
  screenshot_b64?: string | null;
  cookies?: Record<string, string> | null;
  error_message?: string | null;
  cookies_count: number;
};

export function BrowserLoginPanel({ onConfirmed }: BrowserLoginPanelProps) {
  const [session, setSession] = useState<SessionState | null>(null);
  const [captchaText, setCaptchaText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmittingCaptcha, setIsSubmittingCaptcha] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const confirmedRef = useRef(false);

  function clearPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function startSession() {
    setIsLoading(true);
    setError(null);
    setCaptchaText("");
    confirmedRef.current = false;
    clearPolling();

    try {
      const response = await http.post<SessionState>("/browser-login/start");
      const s = response.data;
      setSession(s);
      // Start polling
      pollRef.current = setInterval(() => pollSession(s.session_id), 1500);
    } catch (caught) {
      const detail = axios.isAxiosError(caught) ? caught.response?.data?.detail : String(caught);
      setError(typeof detail === "string" ? detail : "启动浏览器登录失败");
    } finally {
      setIsLoading(false);
    }
  }

  async function pollSession(sessionId: string) {
    try {
      const response = await http.get<SessionState>(`/browser-login/${sessionId}`);
      const s = response.data;
      setSession(s);

      if (s.state === "login_success" && s.cookies && !confirmedRef.current) {
        confirmedRef.current = true;
        clearPolling();
        await importCookies(sessionId);
      } else if (s.state === "expired" || s.state === "login_failed" || s.state === "error") {
        clearPolling();
        setError(s.error_message || s.status_text || "登录失败");
      }
    } catch {
      // Silently retry on next poll
    }
  }

  async function importCookies(sessionId: string) {
    try {
      const response = await http.post<{ ok: boolean; account: PlatformAccount }>(
        `/browser-login/${sessionId}/import-cookies`
      );
      onConfirmed(response.data.account);
    } catch (caught) {
      const detail = axios.isAxiosError(caught) ? caught.response?.data?.detail : String(caught);
      setError(typeof detail === "string" ? detail : "导入 Cookie 失败");
      setSession((prev) => prev ? { ...prev, state: "error" } : prev);
    }
  }

  async function submitCaptcha() {
    if (!session?.session_id || !captchaText.trim()) return;
    setIsSubmittingCaptcha(true);
    try {
      await http.post(`/browser-login/${session.session_id}/captcha`, {
        captcha_text: captchaText.trim(),
      });
      setCaptchaText("");
      setError(null);
      // Polling will pick up the state change
    } catch (caught) {
      const detail = axios.isAxiosError(caught) ? caught.response?.data?.detail : String(caught);
      setError(typeof detail === "string" ? detail : "提交验证码失败");
    } finally {
      setIsSubmittingCaptcha(false);
    }
  }

  async function cancelSession() {
    clearPolling();
    if (session?.session_id) {
      try {
        await http.delete(`/browser-login/${session.session_id}`);
      } catch { /* ignore */ }
    }
    setSession(null);
    setError(null);
  }

  useEffect(() => {
    void startSession();
    return () => clearPolling();
  }, []);

  const isCaptcha = session?.state === "captcha_needed";
  const isSuccess = session?.state === "login_success";
  const isRunning = session && !["login_success", "expired", "login_failed", "error"].includes(session.state);

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      {/* QR / Screenshot display */}
      <Card
        styles={{
          body: {
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: 16,
            minHeight: 240,
            background: "#1f1f1f",
          },
        }}
        style={{ borderColor: "#303030" }}
      >
        {isCaptcha && session.captcha_image_b64 ? (
          <div style={{ textAlign: "center" }}>
            <img
              src={`data:image/png;base64,${session.captcha_image_b64}`}
              alt="验证码"
              style={{
                maxWidth: "100%",
                maxHeight: 180,
                borderRadius: 8,
                border: "2px solid #ff4d4f",
                marginBottom: 12,
              }}
            />
            <Text style={{ color: "#ff4d4f", fontSize: 13 }}>
              检测到验证码，请在下方输入验证码
            </Text>
          </div>
        ) : session?.qr_image_b64 ? (
          <img
            src={`data:image/png;base64,${session.qr_image_b64}`}
            alt="小红书登录二维码"
            style={{
              width: 180,
              height: 180,
              borderRadius: 8,
              background: "#fff",
              padding: 8,
            }}
          />
        ) : session?.screenshot_b64 ? (
          <img
            src={`data:image/png;base64,${session.screenshot_b64}`}
            alt="浏览器截图"
            style={{
              maxWidth: "100%",
              maxHeight: 260,
              borderRadius: 8,
              border: "1px solid #303030",
            }}
          />
        ) : (
          <div
            style={{
              width: 180,
              height: 180,
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
            {isLoading ? "..." : <ScanOutlined />}
          </div>
        )}
      </Card>

      {/* Status */}
      <div style={{ textAlign: "center" }}>
        <Text strong style={{ display: "block", color: "rgba(255,255,255,0.88)" }}>
          {isCaptcha ? "需要输入验证码" : session?.status_text || "准备中..."}
        </Text>
        {isSuccess ? (
          <Text type="success" style={{ display: "block", marginTop: 4 }}>
            Cookie 已获取，正在绑定账号...
          </Text>
        ) : null}
      </div>

      {/* Captcha input */}
      {isCaptcha ? (
        <Space.Compact style={{ width: "100%" }}>
          <Input
            placeholder="请输入验证码"
            value={captchaText}
            onChange={(e) => setCaptchaText(e.target.value)}
            onPressEnter={submitCaptcha}
            disabled={isSubmittingCaptcha}
            style={{ background: "#262626", borderColor: "#303030", color: "#fff" }}
          />
          <Button
            type="primary"
            danger
            onClick={submitCaptcha}
            loading={isSubmittingCaptcha}
            disabled={!captchaText.trim()}
          >
            提交
          </Button>
        </Space.Compact>
      ) : null}

      {/* Error */}
      {error ? (
        <Alert type="error" message={error} showIcon closable onClose={() => setError(null)} />
      ) : null}

      {/* Actions */}
      <Space style={{ width: "100%", justifyContent: "center" }}>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => {
            cancelSession();
            void startSession();
          }}
          loading={isLoading}
        >
          刷新
        </Button>
        {isRunning ? (
          <Button onClick={cancelSession} danger>
            取消
          </Button>
        ) : null}
      </Space>

      {/* Help text */}
      <Card
        size="small"
        style={{ background: "#1a1a1a", borderColor: "#303030" }}
        styles={{ body: { padding: 12 } }}
      >
        <Text style={{ color: "rgba(255,255,255,0.45)", fontSize: 12 }}>
          此方式使用真实浏览器登录小红书。如果出现验证码，请查看上方截图并输入验证码。
          整个过程在服务器端浏览器中完成，登录后 Cookie 会自动同步到账号系统。
        </Text>
      </Card>
    </Space>
  );
}
