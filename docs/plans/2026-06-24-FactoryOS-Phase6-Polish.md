# Factory OS Phase 6: 收尾 + 部署

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development。
> 依赖: Phase 0-5 全部完成

---

## Task 6-1: 响应式适配

**说明：** 确保所有页面在 1024px / 1440px / 1920px 下正常显示。

### 修改点

```tsx
// frontend/src/components/sidebar.tsx — 添加响应式折叠
'use client';
import { useState } from 'react';
import { Menu } from 'lucide-react';

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);

  // collapsed 时只显示图标，隐藏文字
  // 宽度从 224px 变成 64px
  // 小屏幕自动折叠
}
```

```css
/* frontend/src/app/globals.css — 追加响应式规则 */

/* 小于 1024px：自动折叠侧边栏 */
@media (max-width: 1024px) {
  .sidebar { width: 64px; }
  .sidebar .nav-label { display: none; }
  .main-content { margin-left: 64px; }
}

/* 小于 768px：隐藏侧边栏，使用顶部汉堡菜单 */
@media (max-width: 768px) {
  .sidebar { display: none; }
  .main-content { margin-left: 0; }
}
```

---

## Task 6-2: 状态处理

**说明：** 检查所有页面的加载态、空态、错误态、边界态。

### 统一加载态组件

```tsx
// frontend/src/components/loading-state.tsx
'use client';

export function LoadingState({ text = '加载中...' }: { text?: string }) {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="flex flex-col items-center gap-3">
        <div className="w-6 h-6 border-2 border-[var(--border-default)] border-t-[var(--accent-blue)] rounded-full animate-spin" />
        <div className="text-xs text-[var(--text-muted)]">{text}</div>
      </div>
    </div>
  );
}
```

### 统一错误态组件

```tsx
// frontend/src/components/error-state.tsx
'use client';

import { AlertTriangle, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="flex flex-col items-center gap-3">
        <AlertTriangle className="h-8 w-8 text-[var(--accent-red)]" />
        <div className="text-sm text-[var(--text-secondary)]">{message}</div>
        {onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-2 text-xs text-[var(--accent-blue)] hover:underline"
          >
            <RefreshCw className="h-3 w-3" />
            重试
          </button>
        )}
      </div>
    </div>
  );
}
```

---

## Task 6-3: Docker 部署配置

**文件：**
- Modify: `docker-compose.yml`
- Create: `api/Dockerfile`
- Create: `frontend/Dockerfile`

### api/Dockerfile

```dockerfile
# api/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt fastapi uvicorn sqlalchemy python-jose[cryptography]

# 复制代码
COPY api/ ./api/
COPY core/ ./core/
COPY config/ ./config/
COPY data/ ./data/

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### frontend/Dockerfile

```dockerfile
# frontend/Dockerfile
FROM node:18-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:18-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]
```

### docker-compose.yml

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build:
      context: .
      dockerfile: api/Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - DATABASE_URL=sqlite:///app/data/factory.db
      - JWT_SECRET=${JWT_SECRET:-factory-os-prod-secret}
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - api
    restart: unless-stopped
```

---

## Task 6-4: 生产环境配置

### 环境变量

```bash
# .env.production
JWT_SECRET=<generate-a-strong-secret>
DATABASE_URL=postgresql://user:pass@host:5432/factory_os
NEXT_PUBLIC_API_URL=https://api.factory-os.com
```

### nginx 反向代理配置

```nginx
# nginx.conf
server {
    listen 80;
    server_name factory-os.com;

    location / {
        proxy_pass http://frontend:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/ {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Phase 6 完成检查清单

- [ ] 响应式布局：1024px / 1440px / 1920px 均正常
- [ ] 加载态：每个数据区域有 LoadingState
- [ ] 空态：无数据时展示 EmptyState
- [ ] 错误态：API 错误时展示 ErrorState + 重试
- [ ] Docker 构建通过：`docker-compose build`
- [ ] `npm run build` 无错误
- [ ] `pytest api/tests/ -v` 全部通过
- [ ] 提交 commit: `feat: Phase 6 — 收尾 + 部署配置`

---

## 全项目完成检查清单

- [x] Phase 0: Design System 组件库
- [x] Phase 1: 后端骨架 + Priority Engine
- [x] Phase 2: 指挥中心（Decision Center）
- [x] Phase 3: 4 个业务中心页面
- [x] Phase 4: 数据中枢 + 系统设置
- [x] Phase 5: AI 神经系统
- [x] Phase 6: 响应式 + 错误态 + Docker

**Factory OS 上线就绪。**
