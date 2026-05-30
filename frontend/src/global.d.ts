/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BUILD_SHA: string;
  readonly VITE_BUILD_TIME: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

import "axios";

declare module "axios" {
  export interface AxiosRequestConfig {
    _silent?: boolean;
  }
}
