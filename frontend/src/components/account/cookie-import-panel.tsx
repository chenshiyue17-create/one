import { Alert, Button, Checkbox, Form, Input, Space, Divider, Select, message, Typography } from "antd";
import { ImportOutlined, ChromeOutlined } from "@ant-design/icons";
import { useState } from "react";

import { importXhsCookieAccount, importXhsCookieFromBrowser } from "../../lib/api";
import type { PlatformAccount } from "../../types";

const { Text } = Typography;

type CookieImportPanelProps = {
  accountType: "pc" | "creator";
  onImported: (account: PlatformAccount) => void;
};

export function CookieImportPanel({ accountType, onImported }: CookieImportPanelProps) {
  const [cookieString, setCookieString] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncCreator, setSyncCreator] = useState(false);
  const [browserType, setBrowserType] = useState<"chrome" | "edge" | "safari" | "auto">("chrome");

  async function handleImport() {
    setError(null);
    if (!cookieString.includes("=")) {
      setError("请粘贴完整 Cookie 字符串。");
      return;
    }

    setIsSubmitting(true);
    try {
      const account = await importXhsCookieAccount({
        sub_type: accountType,
        cookie_string: cookieString.trim(),
        sync_creator: accountType === "pc" ? syncCreator : undefined
      });
      onImported(account);
      setCookieString("");
      message.success("账号导入成功");
    } catch (caught: any) {
      setError(caught?.response?.data?.detail || "Cookie 无效或已过期。");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleAutoExtract() {
    setError(null);
    setIsExtracting(true);
    try {
      const account = await importXhsCookieFromBrowser({
        sub_type: accountType,
        browser_type: browserType,
        sync_creator: accountType === "pc" ? syncCreator : undefined
      });
      onImported(account);
      message.success(`已从 ${browserType === "auto" ? "浏览器" : browserType} 成功导入账号`);
    } catch (caught: any) {
      setError(caught?.response?.data?.detail || "无法从浏览器获取 Cookie，请确保你已在该浏览器登录小红书，并尝试关闭浏览器后重试。");
    } finally {
      setIsExtracting(false);
    }
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: "100%" }}>
      <div style={{ padding: "12px", background: "rgba(22, 119, 255, 0.08)", borderRadius: 8, border: "1px solid rgba(22, 119, 255, 0.2)" }}>
        <Text style={{ display: "block", marginBottom: 12, color: "rgba(255,255,255,0.65)", fontSize: 12 }}>
          免扫码！自动从本地安装的浏览器中提取已登录的小红书账号。
        </Text>
        <Space.Compact style={{ width: "100%" }}>
          <Select
            value={browserType}
            onChange={setBrowserType}
            style={{ width: 120 }}
            options={[
              { label: "Chrome", value: "chrome" },
            ]}
          />
          <Button
            type="primary"
            icon={<ChromeOutlined />}
            onClick={handleAutoExtract}
            loading={isExtracting}
            style={{ flex: 1 }}
          >
            从 Chrome 一键导入
          </Button>
        </Space.Compact>
      </div>

      <Divider plain style={{ margin: "4px 0", borderColor: "#303030" }}>
        <span style={{ color: "rgba(255,255,255,0.25)", fontSize: 12 }}>或手动粘贴</span>
      </Divider>

      <Form layout="vertical">
        <Form.Item label={<span style={{ color: "rgba(255,255,255,0.88)" }}>Cookie 字符串</span>}>
          <Input.TextArea
            value={cookieString}
            onChange={(e) => setCookieString(e.target.value)}
            placeholder="a1=...; web_session=...;"
            rows={4}
            style={{ background: "#1f1f1f", borderColor: "#303030", color: "rgba(255,255,255,0.88)" }}
          />
        </Form.Item>
      </Form>

      {accountType === "pc" ? (
        <Checkbox
          checked={syncCreator}
          onChange={(event) => setSyncCreator(event.target.checked)}
          style={{ color: "rgba(255,255,255,0.88)" }}
        >
          导入后同步 Creator 账号
        </Checkbox>
      ) : null}

      {error ? <Alert type="error" message={error} showIcon /> : null}

      <Button
        block
        icon={<ImportOutlined />}
        onClick={handleImport}
        loading={isSubmitting}
        disabled={!cookieString}
      >
        {isSubmitting ? "校验中..." : "手动校验并导入"}
      </Button>
    </Space>
  );
}
