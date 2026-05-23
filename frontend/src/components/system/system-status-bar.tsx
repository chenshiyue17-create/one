import { CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined, ReloadOutlined, WarningOutlined } from "@ant-design/icons";
import { Button, Space, Tag, Tooltip, Typography } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";

import { apiUrl } from "../../lib/api";

const { Text } = Typography;

type StatusCheck = {
  name: string;
  ok: boolean;
  status: "online" | "degraded" | "offline";
  http_code: number | null;
  latency_ms: number;
  url: string;
  message: string;
};

type SystemStatus = {
  ok: boolean;
  status: "online" | "degraded" | "offline";
  checked_at: string;
  runtime?: {
    pid: number;
    frontend_built_at: string | null;
    memory: {
      total_label: string;
      available_label: string;
      used_percent: number | null;
    };
    swap: {
      total_label: string;
      free_label: string;
      used_percent: number | null;
    };
  };
  tasks?: {
    running_count: number;
    failed_count: number;
    latest_error: string | null;
    latest_success_at: string | null;
  };
  accounts?: {
    total_count: number;
    active_count: number;
    expired_count: number;
    latest_status_message: string | null;
  };
  checks: StatusCheck[];
};

function offlineStatus(message: string): SystemStatus {
  return {
    ok: false,
    status: "offline",
    checked_at: new Date().toISOString(),
    checks: [
      {
        name: "本地后端",
        ok: false,
        status: "offline",
        http_code: null,
        latency_ms: 0,
        url: apiUrl("/system/status"),
        message,
      },
    ],
  };
}

function statusColor(status: SystemStatus["status"]) {
  if (status === "online") return "success";
  if (status === "degraded") return "warning";
  return "error";
}

function statusText(status: SystemStatus["status"]) {
  if (status === "online") return "全部在线";
  if (status === "degraded") return "部分异常";
  return "本地离线";
}

function statusIcon(status: SystemStatus["status"], loading: boolean) {
  if (loading) return <LoadingOutlined />;
  if (status === "online") return <CheckCircleOutlined />;
  if (status === "degraded") return <WarningOutlined />;
  return <CloseCircleOutlined />;
}

export function SystemStatusBar() {
  const [status, setStatus] = useState<SystemStatus>(() => offlineStatus("等待检测"));
  const [loading, setLoading] = useState(false);

  const loadStatus = useCallback(async () => {
    const started = performance.now();
    setLoading(true);
    try {
      const response = await fetch(apiUrl("/system/status"), { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = (await response.json()) as SystemStatus;
      const localCheck = data.checks.find((item) => item.name === "本地后端");
      if (localCheck) {
        localCheck.latency_ms = Math.round(performance.now() - started);
      }
      setStatus(data);
    } catch (error) {
      setStatus(offlineStatus(error instanceof Error ? error.message : "无法连接本地后端"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadStatus();
    const timer = window.setInterval(() => void loadStatus(), 10_000);
    return () => window.clearInterval(timer);
  }, [loadStatus]);

  const checkedAt = useMemo(() => {
    try {
      return new Date(status.checked_at).toLocaleTimeString("zh-CN", { hour12: false });
    } catch {
      return "-";
    }
  }, [status.checked_at]);

  const builtAt = useMemo(() => {
    if (!status.runtime?.frontend_built_at) return "-";
    try {
      return new Date(status.runtime.frontend_built_at).toLocaleString("zh-CN", { hour12: false });
    } catch {
      return "-";
    }
  }, [status.runtime?.frontend_built_at]);

  const detail = (
    <div className="system-status-detail">
      {status.runtime ? (
        <div className="system-status-runtime">
          <Text type="secondary">PID：{status.runtime.pid}</Text>
          <Text type="secondary">内存：{status.runtime.memory.available_label} 可用 / {status.runtime.memory.total_label}</Text>
          <Text type="secondary">Swap：{status.runtime.swap.free_label} 可用 / {status.runtime.swap.total_label}</Text>
          <Text type="secondary">前端构建：{builtAt}</Text>
        </div>
      ) : null}
      <div className="system-status-runtime">
        <Text type="secondary">运行中任务：{status.tasks?.running_count ?? 0}</Text>
        <Text type="secondary">失败任务：{status.tasks?.failed_count ?? 0}</Text>
        <Text type={status.accounts?.expired_count ? "danger" : "secondary"}>
          账号：{status.accounts?.active_count ?? 0} 正常 / {status.accounts?.expired_count ?? 0} 过期
        </Text>
        {status.tasks?.latest_error ? <Text type="danger">最近错误：{status.tasks.latest_error}</Text> : null}
      </div>
      {status.checks.map((item) => (
        <div className="system-status-row" key={item.name}>
          <span className={item.ok ? "status-dot status-dot-ok" : "status-dot status-dot-bad"} />
          <div className="system-status-row-main">
            <Text strong>{item.name}</Text>
            <Text type="secondary">{item.http_code ?? "无响应"} · {item.latency_ms}ms · {item.message}</Text>
          </div>
        </div>
      ))}
      <Text type="secondary">最后检测：{checkedAt}</Text>
    </div>
  );

  return (
    <div className="system-status-bar">
      <Tooltip title={detail} placement="bottomRight" color="#141414">
        <Tag color={statusColor(status.status)} icon={statusIcon(status.status, loading)} className="system-status-tag">
          {statusText(status.status)}
        </Tag>
      </Tooltip>
      <Space size={6}>
        {status.runtime ? <Text type="secondary" className="system-status-runtime-mini">PID {status.runtime.pid}</Text> : null}
        <Text type="secondary" className="system-status-runtime-mini">任务 {status.tasks?.running_count ?? 0}</Text>
        <Text type="secondary" className="system-status-time">{checkedAt}</Text>
        <Button type="text" size="small" icon={<ReloadOutlined />} onClick={() => void loadStatus()} />
      </Space>
    </div>
  );
}
