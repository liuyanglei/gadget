const CATEGORIES=['A股公告','分红派息','公司报告','监管动态','宏观数据','政策解读'];
const state={payload:null,articles:[],query:'',category:'全部',visible:25};
const byId=id=>document.getElementById(id);
const escapeHtml=(value='')=>String(value).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'})[c]);
const formatTime=value=>{const date=new Date(value);return Number.isNaN(date.getTime())?'时间未知':new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(date)};
const showToast=message=>{const toast=byId('toast');toast.textContent=message;toast.classList.add('show');setTimeout(()=>toast.classList.remove('show'),2200)};

function categoryLimits(){return state.payload.category_limits||Object.fromEntries(CATEGORIES.map(category=>[category,state.payload.per_category_limit||500]))}
function renderOverview(byteSize){
  const {payload,articles}=state;const nowDate=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai'}).format(new Date());
  const today=articles.filter(item=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai'}).format(new Date(item.published_at))===nowDate).length;
  const sources=new Set(articles.map(item=>String(item.source||'').split(' · ')[0]).filter(Boolean));
  byId('totalArticles').textContent=articles.length.toLocaleString('zh-CN');byId('todayArticles').textContent=today.toLocaleString('zh-CN');byId('sourceCount').textContent=sources.size;byId('dataSize').textContent=`${(byteSize/1024/1024).toFixed(2)} MB`;
  byId('contentMode').textContent=payload.content_mode==='official_full_text_zh_with_attachments'?'中文官方全文 + 附件':'未知模式';byId('backfillDays').textContent=`最近 ${payload.backfill_days||2} 天`;
  const limits=Object.values(categoryLimits());byId('categoryLimit').textContent=`${Math.min(...limits)}—${Math.max(...limits)} 篇`;byId('lastUpdate').textContent=formatTime(payload.updated_at);byId('updatedText').textContent=`数据更新：${formatTime(payload.updated_at)}`;
}

function renderCategories(){const limits=categoryLimits();byId('categoryGrid').innerHTML=CATEGORIES.map(category=>{const limit=limits[category];const count=state.articles.filter(item=>item.category===category).length;const ratio=Math.min(100,count/limit*100);return`<article class="category-card"><header><h3>${category}</h3><strong>${count}</strong></header><p>容量 ${count} / ${limit} · 使用 ${ratio.toFixed(1)}%</p><div class="progress"><i style="width:${ratio}%"></i></div></article>`}).join('')}
function renderSettings(){const limits=categoryLimits();byId('limitInputs').innerHTML=CATEGORIES.map(category=>`<div class="limit-field"><label>${category}<input type="number" min="20" max="5000" step="10" value="${limits[category]}" data-limit-category="${category}"></label><small>当前已收录 ${state.articles.filter(item=>item.category===category).length} 篇</small></div>`).join('')}
function settingsFromForm(){return{category_limits:Object.fromEntries([...document.querySelectorAll('[data-limit-category]')].map(input=>[input.dataset.limitCategory,Math.min(5000,Math.max(20,Number(input.value)||500))]))}}
function downloadJson(payload,name){const blob=new Blob([JSON.stringify(payload,null,2)+'\n'],{type:'application/json'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=name;link.click();URL.revokeObjectURL(url)}

function qualityChecks(){const articles=state.articles;const ids=articles.map(x=>x.id);const titleKeys=articles.map(x=>String(x.title||'').replace(/[^\p{L}\p{N}]+/gu,'').toLowerCase());const validDates=articles.filter(x=>!Number.isNaN(new Date(x.published_at).getTime())).length;const limits=categoryLimits();const checks=[
  ['正文完整度',articles.filter(x=>String(x.content||'').trim().length<180).length,'正文少于 180 字'],
  ['重复 ID',ids.length-new Set(ids).size,'记录 ID 重复'],
  ['重复标题',titleKeys.length-new Set(titleKeys).size,'标准化标题重复'],
  ['栏目归类',articles.filter(x=>!CATEGORIES.includes(x.category)).length,'不属于有效栏目'],
  ['发布时间',articles.length-validDates,'时间格式无效'],
  ['来源字段',articles.filter(x=>!x.source).length,'缺少官方来源'],
  ['附件解析',articles.filter(x=>String(x.source||'').startsWith('上海证券交易所')&&Number(x.attachment_stats?.pages||0)<1).length,'交易所公告缺少 PDF 页数'],
  ['栏目容量',CATEGORIES.filter(category=>articles.filter(x=>x.category===category).length>limits[category]).length,'栏目记录数超过配置上限'],
];return checks}
function renderQuality(){const checks=qualityChecks();byId('qualityGrid').innerHTML=checks.map(([name,count,description])=>`<article class="quality-item ${count?'fail':''}"><i>${count?'!':'✓'}</i><div><strong>${name}：${count?'发现 '+count+' 条':'通过'}</strong><p>${description}</p></div></article>`).join('');const failures=checks.reduce((sum,item)=>sum+item[1],0);const health=byId('overallHealth');health.textContent=failures?'发现数据问题':'系统健康';health.className=`health-pill ${failures?'bad':'ok'}`}

function filteredArticles(){const query=state.query.toLocaleLowerCase('zh-CN');return state.articles.filter(item=>(state.category==='全部'||item.category===state.category)&&(!query||`${item.title} ${item.source} ${item.content}`.toLocaleLowerCase('zh-CN').includes(query)))}
function renderTable(){const matches=filteredArticles();const visible=matches.slice(0,state.visible);byId('resultCount').textContent=`共 ${matches.length} 条，显示 ${visible.length} 条`;byId('articleRows').innerHTML=visible.length?visible.map(item=>`<tr><td>${escapeHtml(item.category)}</td><td>${escapeHtml(item.title)}</td><td>${escapeHtml(item.source)}</td><td>${escapeHtml(formatTime(item.published_at))}</td><td>${String(item.content||'').length.toLocaleString('zh-CN')} 字</td></tr>`).join(''):'<tr><td colspan="5">没有匹配记录</td></tr>';byId('loadMore').hidden=visible.length>=matches.length}

async function loadWorkflowRuns(){try{const response=await fetch('https://api.github.com/repos/liuyanglei/gadget/actions/runs?per_page=8',{headers:{Accept:'application/vnd.github+json'}});if(!response.ok)throw new Error(`HTTP ${response.status}`);const payload=await response.json();const runs=(payload.workflow_runs||[]).filter(run=>['Update finance news','pages build and deployment'].includes(run.name)).slice(0,6);byId('workflowRuns').innerHTML=runs.length?runs.map(run=>`<div class="run-item"><a href="${escapeHtml(run.html_url)}" target="_blank" rel="noopener">${escapeHtml(run.name)}</a><time>${escapeHtml(formatTime(run.created_at))}</time><span class="run-status ${escapeHtml(run.conclusion||'')}">${escapeHtml(run.conclusion||run.status)}</span></div>`).join(''):'<p>暂无公开运行记录。</p>'}catch(error){byId('workflowRuns').innerHTML='<p>GitHub 运行状态暂时无法读取，请通过右上角入口查看。</p>'}}

async function fetchLatestData(){const stamp=Date.now();const local=`../data/news.json?v=${stamp}`;const raw=`https://raw.githubusercontent.com/liuyanglei/gadget/main/data/news.json?v=${stamp}`;const localHost=['localhost','127.0.0.1'].includes(location.hostname);const urls=localHost?[local,raw]:[raw,local];let lastError;for(const url of urls){try{const response=await fetch(url,{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}`);const text=await response.text();return{text,payload:JSON.parse(text)}}catch(error){lastError=error;}}throw lastError}
async function loadData(){byId('overallHealth').textContent='检测中';byId('overallHealth').className='health-pill';try{const {text,payload}=await fetchLatestData();state.payload=payload;state.articles=Array.isArray(payload.articles)?payload.articles:[];state.visible=25;renderOverview(new Blob([text]).size);renderCategories();renderSettings();renderQuality();renderTable();showToast('后台数据已刷新')}catch(error){console.error(error);byId('overallHealth').textContent='数据加载失败';byId('overallHealth').className='health-pill bad';showToast('无法读取 news.json')}}

byId('categoryFilter').innerHTML+=[...CATEGORIES].map(category=>`<option value="${category}">${category}</option>`).join('');
byId('refreshButton').addEventListener('click',()=>{loadData();loadWorkflowRuns()});byId('articleSearch').addEventListener('input',event=>{state.query=event.target.value.trim();state.visible=25;renderTable()});byId('categoryFilter').addEventListener('change',event=>{state.category=event.target.value;state.visible=25;renderTable()});byId('loadMore').addEventListener('click',()=>{state.visible+=25;renderTable()});
byId('exportButton').addEventListener('click',()=>{if(!state.payload)return;const blob=new Blob([JSON.stringify(state.payload,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=`finance-news-${new Date().toISOString().slice(0,10)}.json`;link.click();URL.revokeObjectURL(url);showToast('数据文件已导出')});
byId('downloadSettings').addEventListener('click',()=>{downloadJson(settingsFromForm(),'settings.json');showToast('配置文件已下载')});
byId('saveSettings').addEventListener('click',async()=>{const text=JSON.stringify(settingsFromForm(),null,2);try{await navigator.clipboard.writeText(text+'\n');showToast('配置已复制，正在打开 GitHub 编辑页')}catch{downloadJson(settingsFromForm(),'settings.json');showToast('已下载配置，请粘贴到 GitHub')}setTimeout(()=>window.open('https://github.com/liuyanglei/gadget/edit/main/data/settings.json','_blank','noopener'),350)});
document.querySelectorAll('.sidebar nav a').forEach(link=>link.addEventListener('click',()=>{document.querySelectorAll('.sidebar nav a').forEach(item=>item.classList.remove('active'));link.classList.add('active')}));
loadData();loadWorkflowRuns();
