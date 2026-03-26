const OUR="benchdepot.com";
const KWS=["workbench","work bench","workbenches","work benches"];
const GH_OWNER="newtonmac",GH_REPO="benchpro",GH_WF="collect.yml";
const CC=["#d29922","#58a6ff","#f85149","#3fb950","#bc8cff","#f0883e","#79c0ff","#ff7b72"];

function toPacific(date){return new Date(date.toLocaleString("en-US",{timeZone:"America/Los_Angeles"}));}
function getPacificHour(iso){return toPacific(new Date(iso)).getHours();}

var trendsChart=null;
async function renderTrendsChart(){
  var el=document.getElementById("trends-chart");
  if(!el)return;
  try{
    var r=await fetch("data/trends.json?t="+Date.now());
    var data=await r.json();
    var kws=data.keywords||{};
    var datasets=[];var i=0;
    for(var kw in kws){
      if(!activeKWs.has(kw))continue;
      var pts=kws[kw].map(function(p){return{x:p.date,y:p.value};});
      datasets.push({label:kw,data:pts,borderColor:CC[i%8],backgroundColor:CC[i%8]+"33",borderWidth:2,pointRadius:1,tension:.3,fill:true});
      i++;
    }
    var ctx=el.getContext("2d");
    if(trendsChart)trendsChart.destroy();
    trendsChart=new Chart(ctx,{type:"line",data:{datasets:datasets},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:"bottom",labels:{color:"#7d8590",font:{family:"'JetBrains Mono'",size:10}}}},scales:{x:{type:"time",time:{unit:"week"},grid:{color:"#21262d"},ticks:{color:"#484f58",font:{size:10}}},y:{grid:{color:"#21262d"},ticks:{color:"#484f58",font:{size:10}},title:{display:true,text:"Search interest (0-100)",color:"#484f58"}}}}});
  }catch(e){console.log("No trends data yet");}
}

let allRuns=[],spChart=null,orgChart=null,compChart=null,hourChart=null,activeKWs=new Set(KWS);
async function sha256(t){const d=new TextEncoder().encode(t),b=await crypto.subtle.digest("SHA-256",d);return Array.from(new Uint8Array(b)).map(x=>x.toString(16).padStart(2,"0")).join("");}
async function attemptLogin(){const i=document.getElementById("pw-input"),e=document.getElementById("pw-error"),p=i.value.trim();if(!p)return;const h=await sha256(p);try{const r=await fetch("data/auth.json"),a=await r.json();if(h===a.hash){sessionStorage.setItem("bp_auth",h);showDashboard();}else{e.classList.remove("hidden");i.value="";i.focus();}}catch{sessionStorage.setItem("bp_auth",h);showDashboard();}}
function logout(){sessionStorage.removeItem("bp_auth");document.getElementById("dashboard").classList.add("hidden");document.getElementById("login-screen").classList.remove("hidden");}
async function checkAuth(){const s=sessionStorage.getItem("bp_auth");if(!s)return false;try{const r=await fetch("data/auth.json"),a=await r.json();return s===a.hash;}catch{return true;}}
async function showDashboard(){document.getElementById("login-screen").classList.add("hidden");document.getElementById("dashboard").classList.remove("hidden");updateTokenStatus();buildKWFilter();await loadData();}
function getToken(){return localStorage.getItem("bp_gh_token")||"";}
function openTokenModal(){document.getElementById("token-modal").classList.remove("hidden");document.getElementById("token-input").value=getToken();}
function closeTokenModal(){document.getElementById("token-modal").classList.add("hidden");}
function saveToken(){const v=document.getElementById("token-input").value.trim();if(v&&!v.startsWith("ghp_")&&!v.startsWith("github_pat_")){document.getElementById("token-error").classList.remove("hidden");return;}localStorage.setItem("bp_gh_token",v);document.getElementById("token-error").classList.add("hidden");closeTokenModal();updateTokenStatus();}
function updateTokenStatus(){const e=document.getElementById("token-status"),t=getToken();e.textContent=t?"\u2713 Token connected":"No token";e.className="token-status"+(t?" connected":"");}
async function triggerRun(){const token=getToken();if(!token){openTokenModal();return;}const btn=document.getElementById("btn-run"),bar=document.getElementById("run-status"),txt=document.getElementById("run-status-text"),tm=document.getElementById("run-status-time");btn.disabled=true;btn.classList.add("running");document.getElementById("run-icon").textContent="\u27F3";document.getElementById("run-label").textContent="Running...";bar.classList.remove("hidden","done","error");txt.textContent="Triggering...";tm.textContent="0s";const t0=Date.now(),tick=setInterval(()=>{tm.textContent=Math.floor((Date.now()-t0)/1000)+"s";},1000);try{const r=await fetch("https://api.github.com/repos/"+GH_OWNER+"/"+GH_REPO+"/actions/workflows/"+GH_WF+"/dispatches",{method:"POST",headers:{Authorization:"Bearer "+token,Accept:"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"},body:JSON.stringify({ref:"main"})});if(!r.ok)throw new Error("API error "+r.status);txt.textContent="Searching Google...";await pollWF(token,txt,t0);clearInterval(tick);tm.textContent=Math.floor((Date.now()-t0)/1000)+"s";bar.classList.add("done");txt.textContent="\u2713 Done!";await loadData();setTimeout(()=>bar.classList.add("hidden"),10000);}catch(e){clearInterval(tick);bar.classList.add("error");txt.textContent="\u2717 "+e.message;}finally{btn.disabled=false;btn.classList.remove("running");document.getElementById("run-icon").textContent="\u25B6";document.getElementById("run-label").textContent="Run now";}}
async function pollWF(token,el,t0){await sleep(3000);const hd={Authorization:"Bearer "+token,Accept:"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"};for(let i=0;i<90;i++){try{const r=await fetch("https://api.github.com/repos/"+GH_OWNER+"/"+GH_REPO+"/actions/workflows/"+GH_WF+"/runs?per_page=3",{headers:hd}),d=await r.json(),run=(d.workflow_runs||[]).find(x=>new Date(x.created_at).getTime()>=t0-10000);if(run){if(run.status==="completed"){if(run.conclusion==="success"){await sleep(5000);return;}throw new Error("Failed: "+run.conclusion);}el.textContent=run.status==="queued"?"Queuing...":"Scraping...";}}catch(e){if(e.message.includes("Failed"))throw e;}await sleep(5000);}throw new Error("Timed out");}
function sleep(ms){return new Promise(r=>setTimeout(r,ms));}
async function loadData(){try{const r=await fetch("data/results.json?t="+Date.now()),d=await r.json();allRuns=d.runs||[];}catch{allRuns=[];}renderAll();}
function getDays(){return parseInt(document.getElementById("days-select").value);}
function cutoff(d){return new Date(Date.now()-d*864e5);}
function isOurs(d){return(d||"").includes(OUR);}
function timeAgo(iso){if(!iso)return"\u2014";const ms=Date.now()-new Date(iso).getTime(),m=Math.floor(ms/6e4);if(m<1)return"just now";if(m<60)return m+"m ago";const h=Math.floor(m/60);return h<24?h+"h ago":Math.floor(h/24)+"d ago";}
function latestPerKW(){const l={};for(const kw of activeKWs){const runs=allRuns.filter(r=>r.keyword===kw);if(!runs.length)continue;let bestSp=null,bestOrg=null,bestShop=null,latest=runs[runs.length-1];for(const r of runs){if(r.sponsored&&r.sponsored.length>0)bestSp=r;if(r.organic&&r.organic.length>0)bestOrg=r;if(r.shopping&&r.shopping.length>0)bestShop=r;}const merged={id:latest.id,timestamp:latest.timestamp,keyword:kw,sponsored:bestSp?bestSp.sponsored:[],organic:bestOrg?bestOrg.organic:[],shopping:bestShop?bestShop.shopping:[]};l[kw]=merged;}return l;}
function filteredRuns(){return allRuns.filter(r=>activeKWs.has(r.keyword));}
function buildKWFilter(){const el=document.getElementById("kw-filter");let h='<button class="kw-btn active" onclick="toggleAllKW(this)">All</button>';KWS.forEach(kw=>{h+='<button class="kw-btn active" data-kw="'+kw+'" onclick="toggleKW(this,\''+kw+'\')">'+kw+'</button>';});el.innerHTML=h;}
function toggleKW(btn,kw){if(activeKWs.has(kw)){activeKWs.delete(kw);btn.classList.remove("active");}else{activeKWs.add(kw);btn.classList.add("active");}document.querySelector('.kw-btn:not([data-kw])').classList.toggle("active",activeKWs.size===KWS.length);renderAll();}
function toggleAllKW(btn){if(activeKWs.size===KWS.length){activeKWs.clear();document.querySelectorAll(".kw-btn").forEach(b=>b.classList.remove("active"));}else{KWS.forEach(k=>activeKWs.add(k));document.querySelectorAll(".kw-btn").forEach(b=>b.classList.add("active"));}renderAll();}
function focusKW(kw){activeKWs.clear();activeKWs.add(kw);document.querySelectorAll(".kw-btn").forEach(b=>{b.classList.toggle("active",b.dataset.kw===kw);});document.querySelector('.kw-btn:not([data-kw])').classList.remove("active");renderAll();}

function renderAvgPositions(){
  var el=document.getElementById("avg-positions");
  if(!el)return;
  var days=getDays(),co=cutoff(days).toISOString();
  var kwStats={};
  for(var kw of activeKWs)kwStats[kw]={spSum:0,spCount:0,orgSum:0,orgCount:0,total:0};
  for(var r of filteredRuns()){
    if(r.timestamp<co)continue;
    var ks=kwStats[r.keyword];
    if(!ks)continue;
    ks.total++;
    for(var s of r.sponsored||[])if(isOurs(s.domain)){ks.spSum+=s.position;ks.spCount++;}
    for(var o of r.organic||[])if(isOurs(o.domain)){ks.orgSum+=o.position;ks.orgCount++;}
  }
  fetch("data/trends.json?t="+Date.now()).then(function(r){return r.json();}).then(function(tdata){
    var tkws=tdata.keywords||{};
    var h="";
    for(var kw of activeKWs){
      var ks=kwStats[kw];
      var spAvg=ks.spCount?(ks.spSum/ks.spCount).toFixed(1):"--";
      var orgAvg=ks.orgCount?(ks.orgSum/ks.orgCount).toFixed(1):"--";
      var spPct=ks.total?Math.round(ks.spCount/ks.total*100):0;
      var trend="--";
      if(tkws[kw]&&tkws[kw].length>0){
        var last=tkws[kw][tkws[kw].length-1];
        trend=last.value+"/100";
      }
      h+="<div class=\"avg-card\"><div class=\"avg-kw\">"+kw+"</div>";
      h+="<div class=\"avg-stats\">";
      h+="<div class=\"avg-stat\"><span class=\"avg-label\">Avg paid</span><span class=\"avg-val\">"+(spAvg!=="--"?"#"+spAvg:spAvg)+"</span></div>";
      h+="<div class=\"avg-stat\"><span class=\"avg-label\">Avg organic</span><span class=\"avg-val\">"+(orgAvg!=="--"?"#"+orgAvg:orgAvg)+"</span></div>";
      h+="<div class=\"avg-stat\"><span class=\"avg-label\">Showing</span><span class=\"avg-val\">"+spPct+"%</span></div>";
      var searchVol={"workbench":"110K","work bench":"27K","workbenches":"22K","work benches":"6.6K"};h+="<div class=\"avg-stat\"><span class=\"avg-label\">Mo. volume</span><span class=\"avg-val trend-val\">"+(searchVol[kw]||"--")+"</span></div><div class=\"avg-stat\"><span class=\"avg-label\">Interest</span><span class=\"avg-val trend-val\">"+trend+"</span></div>";
      h+="</div><div class=\"avg-sources\"><a href=\"https://www.google.com/search?q="+encodeURIComponent(kw)+"\" target=\"_blank\">Google SERP</a><a href=\"https://trends.google.com/trends/explore?geo=US&q="+encodeURIComponent(kw)+"\" target=\"_blank\">Trends</a><a href=\"https://ads.google.com/aw/keywordplanner/home\" target=\"_blank\">Keyword Planner</a></div></div>";
    }
    el.innerHTML=h;
  }).catch(function(){
    var h="";
    for(var kw of activeKWs){
      var ks=kwStats[kw];
      var spAvg=ks.spCount?(ks.spSum/ks.spCount).toFixed(1):"--";
      var orgAvg=ks.orgCount?(ks.orgSum/ks.orgCount).toFixed(1):"--";
      var spPct=ks.total?Math.round(ks.spCount/ks.total*100):0;
      h+="<div class=\"avg-card\"><div class=\"avg-kw\">"+kw+"</div>";
      h+="<div class=\"avg-stats\">";
      h+="<div class=\"avg-stat\"><span class=\"avg-label\">Avg paid</span><span class=\"avg-val\">"+(spAvg!=="--"?"#"+spAvg:spAvg)+"</span></div>";
      h+="<div class=\"avg-stat\"><span class=\"avg-label\">Avg organic</span><span class=\"avg-val\">"+(orgAvg!=="--"?"#"+orgAvg:orgAvg)+"</span></div>";
      h+="<div class=\"avg-stat\"><span class=\"avg-label\">Showing</span><span class=\"avg-val\">"+spPct+"%</span></div>";
      h+="<div class=\"avg-stat\"><span class=\"avg-label\">Mo. volume</span><span class=\"avg-val trend-val\">"+({"workbench":"110K","work bench":"27K","workbenches":"22K","work benches":"6.6K"}[kw]||"--")+"</span></div><div class=\"avg-stat\"><span class=\"avg-label\">Interest</span><span class=\"avg-val trend-val\">--</span></div>";
      h+="</div><div class=\"avg-sources\"><a href=\"https://www.google.com/search?q="+encodeURIComponent(kw)+"\" target=\"_blank\">Google SERP</a><a href=\"https://trends.google.com/trends/explore?geo=US&q="+encodeURIComponent(kw)+"\" target=\"_blank\">Trends</a><a href=\"https://ads.google.com/aw/keywordplanner/home\" target=\"_blank\">Keyword Planner</a></div></div>";
    }
    el.innerHTML=h;
  });
}

function renderAll(){renderTrendsChart();renderAvgPositions();renderStatusCards();renderKWBreakdowns();renderAdvTable();renderOrgTable();renderShopTable();renderSpChart();renderOrgChart();renderCompChart();renderHourChart();}
function renderStatusCards(){const latest=latestPerKW(),el=document.getElementById("status-cards"),banner=document.getElementById("alert-banner"),at=document.getElementById("alert-text");const last=allRuns.length?allRuns[allRuns.length-1].timestamp:null;document.getElementById("last-updated").textContent=last?"Last: "+timeAgo(last):"No data";let h='<div class="status-card"><div class="label">Data points</div><div class="positions"><div class="pos-col"><div class="pos-val" style="font-size:22px">'+filteredRuns().length+'</div></div></div><div class="detail">'+activeKWs.size+' keywords active</div></div>';const oSp={},oOr={};for(const kw of activeKWs){const run=latest[kw];if(run){for(const s of run.sponsored||[])if(isOurs(s.domain))oSp[kw]=s.position;for(const o of run.organic||[])if(isOurs(o.domain))oOr[kw]=o.position;}}for(const kw of activeKWs){const sp=oSp[kw],og=oOr[kw];const sc=sp?sp<=3?"good":sp<=5?"warn":"bad":"none";const oc=og?og<=3?"good":og<=5?"warn":"bad":"none";const shopCount=(latest[kw]&&latest[kw].shopping)?latest[kw].shopping.length:0;h+='<div class="status-card" onclick="focusKW(\''+kw+'\')" style="cursor:pointer"><div class="label">"'+kw+'"</div><div class="positions"><div class="pos-col"><div class="pos-type sp">Paid</div><div class="pos-val '+sc+'">'+(sp?"#"+sp:"\u2014")+'</div></div><div class="pos-col"><div class="pos-type org">Organic</div><div class="pos-val '+oc+'">'+(og?"#"+og:"\u2014")+'</div></div></div><div class="detail">'+(sp&&sp<=3?"\u2713 Top 3 paid ":"")+(og&&og<=3?"\u2713 Top 3 organic ":"")+(shopCount?shopCount+" shopping":"")+'</div></div>';}el.innerHTML=h;if(!filteredRuns().length){banner.classList.add("hidden");return;}banner.classList.remove("hidden");const anyGood=Object.values(oSp).some(p=>p<=3);const allGood=Object.values(oSp).length>0&&Object.values(oSp).every(p=>p<=3);if(allGood)banner.classList.add("good");else banner.classList.remove("good");let bhtml='<div class="banner-grid">';for(const kw of activeKWs){const sp=oSp[kw],og=oOr[kw];const spCls=sp?(sp<=3?"b-good":sp<=5?"b-warn":"b-bad"):"b-none";const ogCls=og?(og<=3?"b-good":og<=5?"b-warn":"b-bad"):"b-none";bhtml+='<div class="banner-kw"><div class="banner-kw-name">'+kw+'</div><div class="banner-positions"><div class="banner-pos"><span class="banner-label">PAID</span><span class="banner-val '+spCls+'">'+(sp?"#"+sp:"--")+'</span></div><div class="banner-pos"><span class="banner-label">ORG</span><span class="banner-val '+ogCls+'">'+(og?"#"+og:"--")+'</span></div></div></div>';}bhtml+='</div>';at.innerHTML=bhtml;}
function renderKWBreakdowns(){const latest=latestPerKW(),el=document.getElementById("keyword-breakdowns");let h='<div class="kw-breakdown">';for(const kw of activeKWs){const run=latest[kw];const sp=run?run.sponsored||[]:[];const org=run?run.organic||[]:[];const shop=run?run.shopping||[]:[];const uSp=sp.find(s=>isOurs(s.domain));const uOr=org.find(o=>isOurs(o.domain));var loc=run?run.location||"US":"";h+='<div class="kw-card"><div class="kw-card-header" onclick="focusKW(\''+kw+'\')"><h3>"'+kw+'"</h3><div class="kw-summary"><span class="kw-badge sp-badge">Paid: '+(uSp?"#"+uSp.position:"--")+'</span><span class="kw-badge org-badge">Organic: '+(uOr?"#"+uOr.position:"--")+'</span><span class="kw-badge shop-badge">Shopping: '+shop.length+'</span></div></div><div class="kw-card-body"><div class="kw-third"><div class="kw-half-label sp-label"><span class="dot sp"></span> Sponsored ('+sp.length+')</div>';if(sp.length){for(const s of sp)h+='<div class="placement-row'+(isOurs(s.domain)?" ours":"")+'"><div class="placement-pos">'+s.position+'</div><div class="placement-domain">'+s.domain+'</div>'+(isOurs(s.domain)?'<span class="placement-tag">US</span>':'')+'</div>';}else h+='<div class="empty">None</div>';h+='</div><div class="kw-third"><div class="kw-half-label org-label"><span class="dot org"></span> Organic ('+org.length+')</div>';if(org.length){for(const o of org)h+='<div class="placement-row'+(isOurs(o.domain)?" ours":"")+'"><div class="placement-pos">'+o.position+'</div><div class="placement-domain">'+o.domain+'</div>'+(isOurs(o.domain)?'<span class="placement-tag">US</span>':'')+'</div>';}else h+='<div class="empty">None</div>';h+='</div><div class="kw-third"><div class="kw-half-label shop-label"><span class="dot shop"></span> Shopping ('+shop.length+')</div>';if(shop.length){for(const s of shop)h+='<div class="placement-row"><div class="placement-pos">'+s.position+'</div><div class="placement-domain">'+s.store+'</div><div class="placement-price">'+s.price+'</div></div>';}else h+='<div class="empty">None</div>';h+='</div></div></div>';}h+='</div>';el.innerHTML=h;}
function buildTable(type,tbodyId){const days=getDays(),co=cutoff(days).toISOString(),tbody=document.getElementById(tbodyId);const stats={};for(const run of filteredRuns()){if(run.timestamp<co)continue;const list=run[type]||[];for(const item of list){const d=item.domain;if(!d)continue;if(!stats[d])stats[d]={count:0,posSum:0,best:99,keywords:new Set()};stats[d].count++;stats[d].posSum+=item.position;stats[d].best=Math.min(stats[d].best,item.position);stats[d].keywords.add(run.keyword);}}const sorted=Object.entries(stats).map(([domain,s])=>({domain,count:s.count,avg:s.posSum/s.count,best:s.best,keywords:[...s.keywords]})).sort((a,b)=>b.count-a.count).slice(0,15);if(!sorted.length){tbody.innerHTML='<tr><td colspan="5" class="empty">No data</td></tr>';return;}const mx=sorted[0].count;const cls=type==="sponsored"?"sp":"org";tbody.innerHTML=sorted.map(r=>{const o=isOurs(r.domain);return'<tr><td class="domain-cell'+(o?" ours":"")+'">'+r.domain+(o?" \u2605":"")+'</td><td><div class="bar-cell"><div class="bar-fill '+cls+'" style="width:'+Math.round(r.count/mx*80)+'px"></div><span class="bar-value">'+r.count+'</span></div></td><td style="font-family:var(--font-mono);font-size:12px;color:'+(r.avg<=3?"var(--accent)":"var(--text-muted)")+'">'+r.avg.toFixed(1)+'</td><td style="font-family:var(--font-mono);font-size:12px">#'+r.best+'</td><td><div class="kw-tags">'+r.keywords.map(k=>'<span class="kw-tag">'+k+'</span>').join("")+'</div></td></tr>';}).join("");}
function renderAdvTable(){buildTable("sponsored","advertisers-tbody");}
function renderOrgTable(){buildTable("organic","organic-tbody");}
function renderShopTable(){const days=getDays(),co=cutoff(days).toISOString(),tbody=document.getElementById("shopping-tbody");const stats={};for(const run of filteredRuns()){if(run.timestamp<co)continue;for(const s of run.shopping||[]){const store=s.store||s.domain||"unknown";if(!stats[store])stats[store]={count:0,posSum:0,best:99,keywords:new Set(),prices:[]};stats[store].count++;stats[store].posSum+=s.position;stats[store].best=Math.min(stats[store].best,s.position);stats[store].keywords.add(run.keyword);stats[store].prices.push(s.price);}}const sorted=Object.entries(stats).map(([store,s])=>({store,count:s.count,avg:s.posSum/s.count,best:s.best,keywords:[...s.keywords]})).sort((a,b)=>b.count-a.count).slice(0,15);if(!sorted.length){tbody.innerHTML='<tr><td colspan="5" class="empty">No shopping data yet</td></tr>';return;}const mx=sorted[0].count;tbody.innerHTML=sorted.map(r=>'<tr><td class="domain-cell">'+r.store+'</td><td><div class="bar-cell"><div class="bar-fill shop" style="width:'+Math.round(r.count/mx*80)+'px"></div><span class="bar-value">'+r.count+'</span></div></td><td style="font-family:var(--font-mono);font-size:12px">'+r.avg.toFixed(1)+'</td><td style="font-family:var(--font-mono);font-size:12px">#'+r.best+'</td><td><div class="kw-tags">'+r.keywords.map(k=>'<span class="kw-tag">'+k+'</span>').join("")+'</div></td></tr>').join("");}
function renderPosChart(type,chartVar,canvasId,dash){const days=getDays(),co=cutoff(days).toISOString(),ctx=document.getElementById(canvasId).getContext("2d");const byKw={};for(const r of filteredRuns()){if(r.timestamp<co)continue;for(const item of r[type]||[])if(isOurs(item.domain))(byKw[r.keyword]=byKw[r.keyword]||[]).push({x:toPacific(new Date(r.timestamp)),y:item.position});}const ds=[];let i=0;for(const[kw,pts]of Object.entries(byKw)){ds.push({label:kw,data:pts,borderColor:CC[i%8],backgroundColor:CC[i%8]+"33",borderWidth:2,pointRadius:3,tension:.3,borderDash:dash?[4,4]:[]});i++;}if(window[chartVar])window[chartVar].destroy();window[chartVar]=new Chart(ctx,{type:"line",data:{datasets:ds},options:chartOpts(days)});}
function renderSpChart(){renderPosChart("sponsored","spChart","sp-chart",false);}
function renderOrgChart(){renderPosChart("organic","orgChart","org-chart",true);}
function renderCompChart(){const days=getDays(),co=cutoff(days).toISOString(),ctx=document.getElementById("comp-chart").getContext("2d");const counts={};for(const r of filteredRuns()){if(r.timestamp<co)continue;for(const s of r.sponsored||[]){if(!s.domain)continue;counts[s.domain]=(counts[s.domain]||0)+1;}}const top5=Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,5).map(e=>e[0]);const byD={};for(const d of top5)byD[d]=[];for(const r of filteredRuns()){if(r.timestamp<co)continue;for(const s of r.sponsored||[])if(top5.includes(s.domain))byD[s.domain].push({x:toPacific(new Date(r.timestamp)),y:s.position});}const ds=top5.map((d,i)=>({label:d+(isOurs(d)?" \u2605":""),data:byD[d],borderColor:CC[i%8],backgroundColor:CC[i%8]+"33",borderWidth:isOurs(d)?3:1.5,pointRadius:isOurs(d)?4:2,tension:.3}));if(compChart)compChart.destroy();compChart=new Chart(ctx,{type:"line",data:{datasets:ds},options:chartOpts(days)});}
function renderHourChart(){const days=getDays(),co=cutoff(days).toISOString(),ctx=document.getElementById("hour-chart").getContext("2d");const hc=new Array(24).fill(0);for(const r of filteredRuns()){if(r.timestamp<co)continue;const h=new Date(r.timestamp).getHours();for(const s of r.sponsored||[])if(!isOurs(s.domain))hc[h]++;}const labels=Array.from({length:24},(_,h)=>(h%12||12)+(h>=12?"PM":"AM"));if(hourChart)hourChart.destroy();hourChart=new Chart(ctx,{type:"bar",data:{labels,datasets:[{label:"Competitor ads",data:hc,backgroundColor:"rgba(210,153,34,.5)",borderColor:"#d29922",borderWidth:1,borderRadius:3}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:"bottom",labels:{color:"#7d8590",font:{family:"'JetBrains Mono'",size:10}}}},scales:{x:{grid:{color:"#21262d"},ticks:{color:"#484f58",font:{size:10}}},y:{grid:{color:"#21262d"},ticks:{color:"#484f58",font:{size:10}}}}}});}
function chartOpts(days){return{responsive:true,maintainAspectRatio:false,plugins:{legend:{position:"bottom",labels:{color:"#7d8590",font:{family:"'JetBrains Mono'",size:10}}}},scales:{x:{type:"time",time:{unit:days<=7?"hour":"day"},grid:{color:"#21262d"},ticks:{color:"#484f58",font:{size:10}}},y:{reverse:true,min:1,max:10,grid:{color:"#21262d"},ticks:{color:"#484f58",font:{family:"'JetBrains Mono'",size:10},stepSize:1,callback:v=>"#"+v},title:{display:true,text:"Position",color:"#484f58"}}}};}
setInterval(loadData,5*60*1000);

function bind(id,evt,fn){var el=document.getElementById(id);if(el)el.addEventListener(evt,fn);}
document.addEventListener("DOMContentLoaded",async function(){
  bind("btn-login","click",attemptLogin);
  bind("pw-input","keydown",function(e){if(e.key==="Enter")attemptLogin();});
  bind("btn-run","click",triggerRun);
  bind("btn-refresh","click",loadData);
  bind("btn-logout","click",logout);
  bind("btn-save-token","click",saveToken);
  bind("btn-cancel-token","click",closeTokenModal);
  bind("btn-token-settings","click",openTokenModal);
  bind("token-input","keydown",function(e){if(e.key==="Enter")saveToken();});
  bind("days-select","change",renderAll);
  if(await checkAuth())showDashboard();
});