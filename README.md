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

目前只采集中文官方公开来源：上海证券交易所上市公司公告，以及中华人民共和国工业和信息化部的经济运行、政策文件和行业统计页面。栏目包括“全部、A股公告、分红派息、公司报告、监管动态、宏观数据、政策解读”。

采集器会读取网页正文，并解析 PDF、Word、Excel 和图片附件；PDF 图片页及独立图片通过中文 OCR 提取文字，Word/Excel 中的表格和名单也会转成可检索正文。只有正文提取成功且达到完整度要求的内容才会发布，不收录摘要记录或境外市场资讯。

`data/news.json` 初始数据回填最近两天，后续每次运行会合并新内容、去重。当前 A股公告保留 5000 篇，其余栏目各保留 500 篇（“全部”只是汇总入口）；上限由 `data/settings.json` 独立控制，可设置为 20—5000 篇。超过上限时会自动移除该栏目发布时间最早的记录。独立运维后台位于 `/admin/`，可以查看数据质量、GitHub Actions 状态并生成栏目配置。工作日通常可更新上百条，周末、节假日或官方来源发布量较少时会低于该数量。内容不构成投资建议。
