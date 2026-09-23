# 财经观察

基于 GitHub Pages、Python 全文采集器和 GitHub Actions 的免费静态财经资讯站。

## 自动更新

工作流 `.github/workflows/update-news.yml` 按北京时间每天 08:00、12:00、16:00、20:00 运行：

1. 安装 `crawler/requirements.txt` 中的依赖；
2. 执行 `crawler/spider.py`；
3. 将正文提取成功的中文官方财经材料写入 `data/news.json`；
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

目前只采集中文官方公开来源，第一版来源为中华人民共和国工业和信息化部的经济运行、政策文件和行业统计页面。只有正文提取成功且达到完整度要求的内容才会发布；不收录摘要记录或境外市场资讯。内容不构成投资建议。
