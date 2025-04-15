# 论文分析系统 Docker 使用指南

## 环境要求

- Docker
- Docker Compose

## 快速开始

### 构建并启动容器

在项目根目录下运行以下命令：

```bash
docker-compose up -d
```

此命令将构建Docker镜像并在后台启动容器。首次构建可能需要几分钟时间。

### 查看日志

```bash
docker-compose logs -f
```

### 停止容器

```bash
docker-compose down
```

## 目录挂载说明

以下目录将从主机挂载到容器中：

- `./data`: 数据库和其他持久化数据
- `./Papers`: 论文PDF文件
- `./Docs`: 文档文件
- `./JSON`: JSON格式的论文数据
- `./Ents`: 实体数据
- `./static`: 静态资源文件
- `./templates`: 模板文件
- `./arxiv`: arXiv元数据和相关资源

## 访问应用

应用启动后，可以通过以下URL访问：

- Web界面: http://localhost:5002
- API文档: http://localhost:5002/api/docs

## 手动构建镜像

如果需要手动构建Docker镜像，可以运行：

```bash
docker build -t paper-analysis-system .
```

## 常见问题排查

### 容器无法启动

检查日志：

```bash
docker-compose logs
```

### 容器启动但无法访问应用

确保5002端口没有被其他应用占用：

```bash
netstat -tuln | grep 5002
```

### 数据目录权限问题

如果遇到权限相关错误，请确保数据目录具有适当的权限：

```bash
chmod -R 777 data Papers Docs JSON Ents
```

## 环境变量

在`docker-compose.yml`文件中可以配置以下环境变量：

- `PYTHONUNBUFFERED=1`: 确保Python输出不被缓冲
- `FLASK_ENV`: Flask环境设置（development或production）
- `FLASK_DEBUG`: 是否启用Flask调试模式（0表示关闭，1表示开启） 