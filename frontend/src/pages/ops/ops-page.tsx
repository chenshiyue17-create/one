import {
  Alert,
  Button,
  Card,
  Col,
  Input,
  Modal,
  Row,
  Select,
  Space,
  Statistic,
  Tag,
  Typography,
  message,
} from "antd";
import { CloudSyncOutlined, ReloadOutlined, SafetyCertificateOutlined, ToolOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";

import { fetchOpsLogs, fetchOpsStatus, runOpsAction, type OpsLogType, type OpsStatus } from "../../lib/api";

const { Text, Title } = Typography;

function actionLabel(action: "restart-service" | "reload-nginx" | "rebuild-frontend" | "deploy-check") {
  if (action === "restart-service") return "重启 one-xhs";
  if (action === "reload-nginx") return "重载 Nginx";
  if (action === "rebuild-frontend") return "重新构建前端";
  return "运行部署检查";
}

export function OpsPage() {
  const [status, setStatus] = useState<OpsStatus | null>(null);
  const [logType, setLogType] = useState<OpsLogType>("service");
  const [logContent, setLogContent] = useState("");
  const [logSource, setLogSource] = useState("");
  const [opsToken, setOpsToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  async function loadStatus() {
    setLoading(true);
    try {
      setStatus(await fetchOpsStatus());
    } catch {
      message.error("运维状态读取失败");
    } finally {
      setLoading(false);
    }
  }

  async function loadLogs(type = logType) {
    setLoading(true);
    try {
      const logs = await fetchOpsLogs(type, 240);
      setLogType(type);
      setLogContent(logs.content);
      setLogSource(logs.source);
    } catch {
      message.error("日志读取失败");
    } finally {
      setLoading(false);
    }
  }

  function confirmAction(action: "restart-service" | "reload-nginx" | "rebuild-frontend" | "deploy-check") {
    Modal.confirm({
      title: actionLabel(action),
      content: "这是受保护的服务器操作。确认后会校验 SYSTEM_OPS_TOKEN，并只执行白名单内的固定命令。",
      okText: "确认执行",
      cancelText: "取消",
      okButtonProps: { danger: action === "restart-service" },
      onOk: async () => {
        setActionLoading(action);
        try {
          const result = await runOpsAction(action, opsToken);
          if (result.ok) {
            message.success(`${actionLabel(action)} 已执行`);
          } else {
            message.warning(result.stderr || result.stdout || "命令返回非 0");
          }
          await loadStatus();
          await loadLogs(action === "reload-nginx" ? "nginx" : action === "rebuild-frontend" ? "deploy" : "service");
        } catch (caught: any) {
          const detail = caught?.response?.data?.detail;
          message.error(detail || caught?.message || "操作失败");
        } finally {
          setActionLoading(null);
        }
      },
    });
  }

  useEffect(() => {
    void loadStatus();
    void loadLogs("service");
  }, []);

  return (
    <div style={{ paddingBottom: 32 }}>
      <div style={{ marginBottom: 24 }}>
        <Text style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1.5, color: "rgba(255,255,255,0.35)" }}>
          Operations
        </Text>
        <Title level={3} style={{ margin: "4px 0", color: "rgba(255,255,255,0.88)" }}>
          运维中心
        </Title>
        <Text type="secondary">查看服务器、任务、日志和部署状态；写操作全部需要二次确认和运维 Token。</Text>
      </div>

      {status?.ops_enabled === false ? (
        <Alert type="warning" showIcon style={{ marginBottom: 16 }} message="SYSTEM_OPS_TOKEN 未配置，高危操作处于禁用状态。" />
      ) : null}

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} md={8}>
          <Card style={{ background: "#1f1f1f", borderColor: "#303030" }}>
            <Statistic
              title="one-xhs 服务"
              value={status?.service.active || "-"}
              prefix={<CloudSyncOutlined />}
              valueStyle={{ color: status?.service.ok ? "#52c41a" : "#ff4d4f" }}
            />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card style={{ background: "#1f1f1f", borderColor: "#303030" }}>
            <Statistic
              title="Nginx 配置"
              value={status?.nginx.ok ? "正常" : "异常"}
              prefix={<SafetyCertificateOutlined />}
              valueStyle={{ color: status?.nginx.ok ? "#52c41a" : "#ff4d4f" }}
            />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card style={{ background: "#1f1f1f", borderColor: "#303030" }}>
            <Statistic
              title="前端构建"
              value={status?.frontend.built ? "已构建" : "缺失"}
              prefix={<ToolOutlined />}
              valueStyle={{ color: status?.frontend.built ? "#52c41a" : "#ff4d4f" }}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title="受保护操作"
        extra={<Button icon={<ReloadOutlined />} loading={loading} onClick={() => void loadStatus()}>刷新状态</Button>}
        style={{ background: "#1f1f1f", borderColor: "#303030", marginBottom: 16 }}
      >
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <Input.Password
            placeholder="输入 SYSTEM_OPS_TOKEN 后才能执行高危操作"
            value={opsToken}
            onChange={(event) => setOpsToken(event.target.value)}
          />
          <Space wrap>
            {(["deploy-check", "reload-nginx", "rebuild-frontend", "restart-service"] as const).map((action) => (
              <Button
                key={action}
                danger={action === "restart-service"}
                loading={actionLoading === action}
                disabled={!status?.ops_enabled || !opsToken}
                onClick={() => confirmAction(action)}
              >
                {actionLabel(action)}
              </Button>
            ))}
          </Space>
        </Space>
      </Card>

      <Card
        title="实时日志"
        extra={
          <Space>
            <Select
              value={logType}
              onChange={(value) => void loadLogs(value)}
              style={{ width: 130 }}
              options={[
                { value: "service", label: "服务日志" },
                { value: "deploy", label: "部署日志" },
                { value: "nginx", label: "Nginx" },
              ]}
            />
            <Button loading={loading} onClick={() => void loadLogs(logType)}>刷新日志</Button>
          </Space>
        }
        style={{ background: "#1f1f1f", borderColor: "#303030" }}
      >
        <Space style={{ marginBottom: 12 }}>
          <Tag>{logSource || "未加载"}</Tag>
          <Text type="secondary">最后检测：{status?.checked_at ? new Date(status.checked_at).toLocaleString("zh-CN", { hour12: false }) : "-"}</Text>
        </Space>
        <pre className="ops-log-viewer">{logContent || "暂无日志"}</pre>
      </Card>
    </div>
  );
}
