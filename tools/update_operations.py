"""Import the user-supplied FY2569 workbook; retain original rows and exact administrative joins."""
import sys,json,re,csv,hashlib,shutil,zipfile,html
from pathlib import Path
from collections import defaultdict
import openpyxl
ROOT=Path(__file__).resolve().parents[1]; D=ROOT/'dist'
src=Path(sys.argv[1]); old=json.loads((D/'ems_data.json').read_text()); keys=['red','yellow','green','other','total']
def norm(s):
 s=re.sub(r'\s+','',str(s or ''))
 return re.sub(r'^(จังหวัด|อำเภอ|ตำบล|เขต|แขวง|จ\.|อ\.|ต\.)','',s)
def load(n):return json.loads((D/(n+'.geojson')).read_text())['features']
P={f['properties']['PROV_CODE']:f['properties'] for f in load('province')}; dm=defaultdict(set);tm=defaultdict(set)
for f in load('district'):
 p=f['properties'];dm[(p['PROV_CODE'],norm(p['AMP_NAM_T']))].add(p['AMP_CODE'])
for f in load('tambon'):
 p=f['properties']
 if str(p['TAM_CODE']).startswith(str(p['AMP_CODE'])):tm[(p['PROV_CODE'],p['AMP_CODE'],norm(p['TAM_NAM_T']))].add(p['TAM_CODE'])
def unique(s):return next(iter(s)) if len(s)==1 else None
s=openpyxl.load_workbook(src,read_only=True,data_only=True)['Query result'];rows=[];control=None;control_row=None
for i,r in enumerate(s.values,1):
 if i==1:continue
 if str(r[0]).strip()=='รวม':control=dict(zip(keys,r[4:9]));control_row=i;continue
 if all(v is None for v in r):continue
 p=str(r[0]).zfill(2); assert p in P,(i,p)
 assert norm(r[1])==norm(P[p]['PROV_NAM_T']),(i,'province conflict')
 vals=list(r[4:9]);assert all(isinstance(v,(int,float)) and v>=0 and int(v)==v for v in vals),(i,vals)
 assert sum(vals[:4])==vals[4],(i,'row reconciliation')
 dn=str(r[2] or '').strip();tn=str(r[3] or '').strip();dc=unique(dm[(p,norm(dn))]);tc=unique(tm[(p,dc,norm(tn))]) if dc else None
 rows.append(dict(source_row=i,p=p,pn=r[1],dn=dn,tn=tn,d=dc,t=tc,**dict(zip(keys,map(int,vals))),status='matched' if tc else 'district_only' if dc else 'province_only'))
tot={k:sum(r[k] for r in rows) for k in keys};assert control==tot,(control,tot)
meta=old['meta'].copy();meta.update(operations_source=src.name,operation_period='ปีงบประมาณ 2569 (1 ต.ค. 2568 – 30 ก.ย. 2569) ตามชื่อไฟล์และขอบเขตที่ผู้ใช้ยืนยัน',operation_fiscal_year=2569,operation_start='2025-10-01',operation_end='2026-09-30',operation_time_resolution='fiscal_year',totals=tot,rows=len(rows),provinces=len({r['p'] for r in rows}),district_matched_ops=sum(r['total'] for r in rows if r['d']),tambon_matched_ops=sum(r['total'] for r in rows if r['t']),unmatched_rows=sum(not r['t'] for r in rows),source_total_row=control_row,source_total_matches=True,updated='2026-10-20')
meta['sources_sha256']={k:v for k,v in meta['sources_sha256'].items() if k!=old['meta']['operations_source']};meta['sources_sha256'][src.name]=hashlib.sha256(src.read_bytes()).hexdigest()
(D/'ems_data.json').write_text(json.dumps(dict(rows=rows,coverage=old['coverage'],meta=meta),ensure_ascii=False,separators=(',',':')))
(D/'Data_Audit.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
fields=['source_row','p','pn','d','dn','t','tn',*keys,'status']
for name,rs in [('EMS_Operations_Detail.csv',rows),('EMS_Unmatched_Locations.csv',[r for r in rows if not r['t']])]:
 with (D/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rs)
(D/'sources').mkdir(exist_ok=True);shutil.copyfile(src,D/'sources'/'EMS_Operations_2569.xlsx')
# Refresh the source paragraph, provenance, and operations scope in the existing UI.
p=D/'index.html';t=p.read_text();t=re.sub(r'<p>สถิติ:.*?</p>',f'<p>สถิติ: {html.escape(src.name)} ชีต Query result รายละเอียดแถว 2–{control_row-1:,}; แถวรวม {control_row:,} ใช้ตรวจสอบ ไม่บวกซ้ำ ปีงบประมาณ 2569 (1 ต.ค. 2568–30 ก.ย. 2569) ตามขอบเขตที่ผู้ใช้ยืนยัน แดง {tot["red"]:,} เหลือง {tot["yellow"]:,} เขียว {tot["green"]:,} อื่น ๆ {tot["other"]:,} รวม {tot["total"]:,} ครั้ง · <a href="sources/EMS_Operations_2569.xlsx">ไฟล์ต้นทางใหม่</a></p>',t)
t=t.replace('ความครอบคลุมปีงบ 2568/2569 เปรียบเทียบตัวเลขตามหัวตาราง ไม่ยืนยันว่าช่วงเวลาสถิติปฏิบัติการตรงกับปีดังกล่าว','ความครอบคลุมปีงบ 2568/2569 เปรียบเทียบตัวเลขตามหัวตาราง ส่วนปฏิบัติการใช้ไฟล์ปีงบประมาณ 2569 ฉบับใหม่ ไม่มีข้อมูลรายเดือนให้คำนวณแนวโน้มภายในปี').replace('ปรับข้อมูล 19 ตุลาคม 2569','ปรับข้อมูล 20 ตุลาคม 2569')
t=t.replace('<script src="app.js"></script><script src="modules.js"></script><script src="complete.js"></script>','<script src="app.js?v=2569-20261020"></script><script src="modules.js?v=2569-20261020"></script><script src="complete.js?v=2569-20261020"></script>');p.write_text(t)
p=D/'modules.js';t=p.read_text().replace("operations:'สถิติปฏิบัติการตามชื่อจังหวัด", "operations:'ปีงบประมาณ 2569 (1 ต.ค. 2568–30 ก.ย. 2569) · สถิติปฏิบัติการตามชื่อจังหวัด");p.write_text(t)
p=D/'app.js';t=p.read_text();t=t.replace("fetch(u).then", "fetch(u+'?v=2569-20261020',{cache:'no-cache'}).then");p.write_text(t)
# Regenerate only the operations section and its full provincial appendix.
prov=defaultdict(lambda:{k:0 for k in keys})
for r in rows:
 for k in keys:prov[r['pn']][k]+=r[k]
rank=sorted(prov.items(),key=lambda v:v[1]['total'],reverse=True)
def table(names,rs):
 return '<table><thead><tr>'+''.join('<th>'+html.escape(h)+'</th>' for h in names)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+(f'{v:,}' if isinstance(v,int) else html.escape(str(v)))+'</td>' for v in row)+'</tr>' for row in rs)+'</tbody></table>'
heads=['จังหวัด','แดง','เหลือง','เขียว','อื่น ๆ','รวม'];trs=lambda entries:[[n,*[v[k] for k in keys]] for n,v in entries]
sec=f'<h2>2. ปฏิบัติการตามระดับความรุนแรง</h2><p class="fact">ปีงบประมาณ 2569 · รวม {tot["total"]:,} ปฏิบัติการ จาก {len(rows):,} แถว ครบ 77 จังหวัด แดง {tot["red"]:,} เหลือง {tot["yellow"]:,} เขียว {tot["green"]:,} อื่น ๆ {tot["other"]:,} ครั้ง</p><p>ใช้ {html.escape(src.name)} แทนข้อมูลเดิมทั้งชุด ไม่บวกยอดกับไฟล์เดิม ช่วง 1 ต.ค. 2568–30 ก.ย. 2569 ตามขอบเขตที่ผู้ใช้ยืนยัน ตารางไม่มีมิติรายเดือนจึงไม่คำนวณแนวโน้มภายในปี</p><h3>Top 5 จำนวนปฏิบัติการรวม</h3>'+table(heads,trs(rank[:5]))+'<h3>Top 5 จำนวนแดง</h3>'+table(['จังหวัด','แดง'],[[n,v['red']] for n,v in sorted(prov.items(),key=lambda v:v[1]['red'],reverse=True)[:5]])+f'<p>จับคู่ตำบลได้ {meta["tambon_matched_ops"]:,} ครั้ง ส่วนที่ยังจับคู่ตำบลไม่ได้ {tot["total"]-meta["tambon_matched_ops"]:,} ครั้ง ใน {meta["unmatched_rows"]:,} แถว คงยอดในจังหวัดและตารางตามต้นฉบับ ไม่ย้ายพื้นที่หรือสร้างพิกัด สถิติคือปฏิบัติการ ไม่ใช่ผู้ป่วยไม่ซ้ำ</p>'
p=D/'EMS_Executive_Brief.html';t=p.read_text();t=re.sub(r'<h2>2\..*?(?=<h2>3\.)',lambda _:sec,t,flags=re.S);t=re.sub(r'(<details>\s*<summary>ปฏิบัติการรายจังหวัดทั้งหมด 77 จังหวัด</summary>).*?</details>',lambda m:m[1]+table(heads,trs(rank))+'</details>',t,flags=re.S);t=t.replace('ปรับปรุง 19 ตุลาคม 2569','ปรับปรุง 20 ตุลาคม 2569');p.write_text(t)
# Replace the stale operations/source discussion, retain all other topics.
p=D/'README_TH.md';t=p.read_text();a=t.index('## แหล่งและยอดตรวจสอบ');b=t.index('รายงานความครอบคลุมหน่วยปฏิบัติการระดับตำบล(1).xlsx',a)
t=t[:a]+f'## แหล่งและยอดตรวจสอบ\n{src.name} ชีต Query result รายละเอียดแถว 2–{control_row-1} จำนวน {len(rows)} แถว แถว {control_row} เป็นยอดรวม ใช้ตรวจสอบ ไม่บวกซ้ำ\nปีงบประมาณ 2569 (1 ต.ค. 2568–30 ก.ย. 2569) ตามชื่อไฟล์และขอบเขตที่ผู้ใช้ยืนยัน ไม่มีมิติรายเดือน ไม่สร้างแนวโน้มภายในปี\n'+ ' '.join(f'{k}={v:,}' for k,v in tot.items())+'\nหน่วยนับปฏิบัติการ ไม่ใช่ผู้ป่วยไม่ซ้ำ ข้อมูลใหม่แทนที่ไฟล์เดิมทั้งชุด\n'+t[b:]
t=re.sub(r'ตรงอำเภอ1572767.*?(?=\nGIS:)',f'ตรงอำเภอ {meta["district_matched_ops"]:,} ครั้ง ตรงตำบล {meta["tambon_matched_ops"]:,} ครั้ง ยังไม่ตรงตำบล {tot["total"]-meta["tambon_matched_ops"]:,} ครั้งใน {meta["unmatched_rows"]} แถว ดู EMS_Unmatched_Locations.csv; คงยอดและชื่อพื้นที่ตามไฟล์ ไม่ย้ายยอดข้ามจังหวัด',t,flags=re.S)
t+='\n## ปรับปรุง 20 ตุลาคม 2569\nแทนข้อมูลปฏิบัติการด้วยไฟล์ปี 2569 ฉบับใหม่ ยืนยันยอดทุกแถวกับแถวรวม ข้อมูลความครอบคลุม ค่าชดเชย และต่างชาติคงเดิม ตัวกรองจังหวัด–อำเภอ–ตำบล การค้นหา Top 5 ตารางทั้งหมด การคลิกแผนที่ และ CSV ใช้ RAW ชุดใหม่เดียวกัน\n';p.write_text(t)
print(json.dumps({'totals':tot,'rows':len(rows),'mapped_district_ops':meta['district_matched_ops'],'mapped_tambon_ops':meta['tambon_matched_ops'],'unmatched_rows':meta['unmatched_rows'],'top5':[(n,v['total']) for n,v in rank[:5]]},ensure_ascii=False))
