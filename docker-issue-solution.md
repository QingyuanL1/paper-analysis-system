# Docker镜像源问题解决方案

根据错误信息，您的Docker仍然在尝试使用registry.docker-cn.com这个已经不可用的镜像源。要解决这个问题，请按照以下步骤操作：

## 1. 更新Docker Desktop配置

1. 打开Docker Desktop应用
2. 点击右上角的设置图标（齿轮图标）
3. 在左侧菜单中选择"Docker Engine"
4. 将配置文件修改为：

```json
{
  "builder": {
    "gc": {
      "defaultKeepStorage": "20GB",
      "enabled": true
    }
  },
  "experimental": false,
  "registry-mirrors": [
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com",
    "https://docker.mirrors.ustc.edu.cn"
  ]
}
```

5. 点击"Apply & Restart"应用更改并重启Docker

## 2. 重新构建项目

Docker重启后，尝试重新构建项目：

```bash
cd /Users/yaowenya/Documents/GitHub/paper-analysis-system
docker compose build
```

## 3. 如果问题仍然存在

可能需要完全重置Docker Desktop：

1. 卸载Docker Desktop
2. 删除Docker相关的配置目录：
   ```bash
   rm -rf ~/Library/Containers/com.docker.docker
   rm -rf ~/Library/Application\ Support/Docker\ Desktop
   rm -rf ~/.docker
   ```
3. 重新安装Docker Desktop
4. 安装后，按照步骤1重新配置镜像源

## 4. 可选：使用官方镜像源

如果国内镜像源连接不稳定，可以尝试不使用任何镜像源，直接使用官方源：

```json
{
  "builder": {
    "gc": {
      "defaultKeepStorage": "20GB",
      "enabled": true
    }
  },
  "experimental": false
}
```

这将使用官方的Docker Hub源，但可能需要网络代理来访问。 