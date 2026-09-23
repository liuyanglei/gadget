# 财经观察

基于 GitHub Pages、Python RSS 采集器和 GitHub Actions 的免费静态财经资讯站。

## 自动更新

工作流 `.github/workflows/update-news.yml` 按北京时间每天 08:00、12:00、16:00、20:00 运行：

1. 安装 `crawler/requirements.txt` 中的依赖；
2. 执行 `crawler/spider.py`；
3. 将公开 RSS 资讯写入 `data/news.json`；
4. 当数据变化时自动提交并推送。

也可以在仓库的 **Actions → Update finance news → Run workflow** 手动触发。

## 本地预览

```bash
python -m pip install -r crawler/requirements.txt
python crawler/spider.py
python -m http.server 8000
```

浏览器打开 `http://localhost:8000/`。直接双击 `index.html` 时，浏览器可能因本地文件安全策略禁止读取 JSON，因此建议使用本地静态服务器预览。

## 数据说明

资讯来自新浪财经、东方财富、Reuters 和 CNBC 的公开 RSS 或公开 RSS 搜索结果。本站只展示标题、摘要、来源、时间及原文链接，版权归原媒体及作者所有；内容不构成投资建议。
