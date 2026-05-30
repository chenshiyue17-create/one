export const appBuildInfo = {
  sha: import.meta.env.VITE_BUILD_SHA,
  builtAt: import.meta.env.VITE_BUILD_TIME,
  projectName: import.meta.env.VITE_PROJECT_NAME,
};

export function getProjectName(): string {
  return appBuildInfo.projectName || "unknown-project";
}

export function getBuildSha(): string {
  return appBuildInfo.sha || "unknown";
}

export function getBuildTime(): string {
  return appBuildInfo.builtAt || "unknown";
}

export function getRuntimeOriginLabel(): string {
  if (typeof window === "undefined") return "unknown";
  const { hostname } = window.location;
  if (hostname === "127.0.0.1" || hostname === "localhost") return "本地页面";
  return "远端页面";
}

export function getRuntimeOriginValue(): string {
  if (typeof window === "undefined") return "unknown";
  return window.location.origin;
}

export function formatBuildLabel(): string {
  const raw = appBuildInfo.builtAt;
  let builtAt = raw;
  try {
    builtAt = new Date(raw).toLocaleString("zh-CN", { hour12: false });
  } catch {
    builtAt = raw;
  }
  return `${getProjectName()} · 版本 ${appBuildInfo.sha} · ${builtAt}`;
}
