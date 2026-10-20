import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const D=new URL('../dist/',import.meta.url);const read=n=>JSON.parse(fs.readFileSync(new URL(n,D),'utf8'));const data=read('ems_data.json'),geo={province:read('province.geojson'),district:read('district.geojson'),tambon:read('tambon.geojson')};
const els=new Map();const elem=id=>{if(!els.has(id))els.set(id,{value:'',checked:false,disabled:false,dataset:{},style:{},options:[],selectedOptions:[],innerHTML:'',textContent:'',querySelectorAll:()=>[]});return els.get(id)};
const context=vm.createContext({console,document:{getElementById:elem,querySelectorAll:()=>[]},Map,Set,Math,Number,JSON,String,Object,Array,URL,Blob,setTimeout,clearTimeout,innerWidth:1200,innerHeight:900});
for(const f of ['app.js','modules.js','complete.js']){let text=fs.readFileSync(new URL(f,D),'utf8');if(f==='complete.js')text=text.replace(/\ninit\(\);\s*$/,'\n');vm.runInContext(text,context,{filename:f});}
context.data=data;context.geo=geo;vm.runInContext('RAW=data.rows;COV=data.coverage;META=data.meta;GEO=geo;build()',context);const run=s=>vm.runInContext(s,context);
let n=0;const check=(a,b)=>{assert.equal(a,b);n++};
check(run('sum(scopeRows()).total'),2620855);check(run('sum(scopeRows()).red'),664966);check(run('sum(scopeRows()).yellow'),1637172);check(run('sum(scopeRows()).green'),149086);check(run('sum(scopeRows()).other'),169631);
// Exercise the actual scopeRows filtering function for every source area, including unmatched selections.
const provinces=[...new Set(data.rows.map(r=>r.p))];for(const p of provinces){elem('province').value=p;check(run('sum(scopeRows()).total'),data.rows.filter(r=>r.p===p).reduce((s,r)=>s+r.total,0));}
const groups=new Map();for(const r of data.rows){const d=r.d||'raw:'+r.dn,t=r.t||'raw:'+r.tn,k=[r.p,d,t].join('|');if(!groups.has(k))groups.set(k,{p:r.p,d,t,total:0});groups.get(k).total+=r.total;}
for(const v of groups.values()){elem('province').value=v.p;elem('district').value=v.d;elem('tambon').value=v.t;check(run('sum(scopeRows()).total'),v.total);}
for(const id of ['province','district','tambon'])elem(id).value='';
run("ACTIVE='operations'");for(const dim of ['province','district','tambon','detail']){elem('allDimension').value=dim;const rows=run('completeRows().rows');const i=dim==='detail'?8:9;check(rows.reduce((s,r)=>s+r[i],0),2620855);if(dim==='detail')check(rows.length,7433);}
for(const level of ['province','district','tambon']){elem('metric').value='total';elem('density').checked=false;const actual=run(`Array.from(CAT.${level}.values()).reduce((s,e)=>s+(value(e,'${level}','total')??0),0)`);check(actual,level==='province'?2620855:level==='district'?data.meta.district_matched_ops:data.meta.tambon_matched_ops);}
elem('metric').value='red_pct';check(run("value(CAT.province.get('40'),'province','red_pct')"),run("AGG.province.get('40').red/AGG.province.get('40').three*100"));
elem('metric').value='total';elem('density').checked=true;check(run("value(CAT.province.get('40'),'province','total')"),run("AGG.province.get('40').total/CAT.province.get('40').area*1000"));
// Data exports and all grouping retain every operation, not just mapped rows or Top 5.
const csv=fs.readFileSync(new URL('EMS_Operations_Detail.csv',D),'utf8').trim().split(/\r?\n/);check(csv.length,7434);
const names=run("Array.from(AGG.province.entries()).sort((a,b)=>b[1].total-a[1].total).slice(0,5).map(([p,a])=>[CAT.province.get(p).name,a.total])");console.log(JSON.stringify({assertions:n,source_rows:data.rows.length,totals:data.meta.totals,top5:names,verified:'all province/district/tambon scopes; full tables; map aggregates; percentages; density; detail CSV'},null,2));
