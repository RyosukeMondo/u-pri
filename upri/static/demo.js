'use strict';
window.UpriDemo = function(){
const fieldNames=["お客様側管理番号", "お問い合わせ番号", "代表お問い合わせ番号", "発送予定日", "発送予定時間区分", "郵便種別", "保冷種別", "元／着払／代引", "書留／セキュリティ／特定記録種別", "送り状種別", "お届け先 検索キー", "お届け先 郵便番号", "お届け先 住所", "お届け先 住所２", "お届け先 住所３", "お届け先 名称", "お届け先 名称２", "お届け先 敬称区分", "お届け先 電話番号", "お届け先 メールアドレス", "お届け先 局留め区分", "お届け先 局留め郵便局名", "お届け先 局留め郵便番号", "郵便局留めメール利用区分", "お届け予定メール利用区分", "ご不在連絡メール利用区分", "ご依頼主 検索キー", "ご依頼主 郵便番号", "ご依頼主 住所", "ご依頼主 住所２", "ご依頼主 住所３", "ご依頼主 名称", "ご依頼主 名称２", "ご依頼主 敬称区分", "ご依頼主 電話番号", "ご依頼主 メールアドレス", "お届け完了メール利用区分", "ご依頼主 お届け通知はがき使用区分", "受注番号", "注文日", "こわれもの区分", "なまもの区分", "ビン類区分", "逆さま厳禁区分", "下積み厳禁区分", "商品サイズ／厚さ区分", "重量合計（ｇ）", "書留 損害要償額", "速達／配達日指定種別", "配達希望日", "配達時間帯区分", "ゆうパック複数個割引", "ゆうパック同一割引", "複数個口数", "記事名１", "記事名２", "フリー項目０１", "フリー項目０２", "フリー項目０３", "フリー項目０４", "フリー項目０５", "フリー項目０６", "フリー項目０７", "フリー項目０８", "フリー項目０９", "フリー項目１０", "代引金額", "代引消費税金額", "お客様指定配送種類", "予備１", "予約・確定識別コード", "コンビニ等判別コード", "コンビニ等受取 通販業者コード", "コンビニ等受取 コンビニコード", "コンビニ等受取 コンビニ名", "コンビニ等受取 店舗コード", "コンビニ等受取 店舗名", "コンビニ等受取 認証番号", "コンビニ等受取 備考１", "コンビニ等受取 備考２", "予備２", "商品番号", "品名", "個数", "単価", "消費税率区分", "金額", "商品番号", "品名", "個数", "単価", "消費税率区分", "金額", "商品番号", "品名", "個数", "単価", "消費税率区分", "金額"];
const drafts=new Map(),batches=new Map();
const clone=x=>structuredClone(x);
function sample(ref,name,item){return {reference:ref,ship_date:today(),recipient:{name,postal_code:'0000000',address1:'デモ県サンプル市1-2-3',address2:'架空の住所・発送不可',address3:'',phone:'0000000000'},sender:{name:'デモ発送センター（架空）',postal_code:'0000000',address1:'デモ県サンプル市4-5-6',address2:'架空の住所・発送不可',address3:'',phone:'0000000000'},items:[{name:item,quantity:1}]};}
function rowsFor(batch){return batch.shipments.map(s=>{const row=Array(99).fill('');Object.entries({0:s.reference,3:s.ship_date.replaceAll('-',''),5:'0',6:'0',7:'0',8:'0',53:'1',68:'UPRI_PREPAID',71:'0'}).forEach(([k,v])=>row[k]=v);for(const [who,o] of [['recipient',11],['sender',27]]){const a=s[who];[a.postal_code,a.address1,a.address2||'',a.address3||'',a.name].forEach((v,i)=>row[o+i]=v);row[o+7]=a.phone;}s.items.forEach((v,i)=>{row[82+i*6]=v.name;row[83+i*6]=String(v.quantity);});return row;});}
function csvText(rows){return rows.map(r=>r.map(v=>`"${String(v).replaceAll('"','""')}"`).join(',')).join('\r\n')+'\r\n';}
function preview(batch){const rows=rowsFor(batch);return {rows,field_names:fieldNames,columns:99,encoding:'UTF-8（デモ専用・発送不可）',bytes:new TextEncoder().encode(csvText(rows)).length,label_generated:false,printing_verified:false};}
function newDraft(batch){const d={id:uuid(),revision:1,batch:clone(batch),created:new Date().toISOString(),updated:new Date().toISOString(),prepared_batch:null};drafts.set(d.id,d);return d;}
function prepare(d){if(d.prepared_batch)return batches.get(d.prepared_batch);const b={id:uuid(),created:new Date().toISOString(),state:'csv_prepared',shipments:d.batch.shipments.map(s=>({reference:s.reference,tracking:null})),csv_url:'',printing_verified:false,operator_events:[],operator_status:'not_reported',batch:clone(d.batch)};b.csv_url=`/v1/batches/${b.id}/csv`;batches.set(b.id,b);d.prepared_batch=b.id;return b;}
const first=newDraft({shipments:[sample('DEMO-DRAFT-001','デモのお届け先A（架空）','書籍セット（発送不可）')]});
const b=prepare(newDraft({shipments:[sample('DEMO-BATCH-001','デモのお届け先B（架空）','文具セット（発送不可）')]}));
b.operator_status='print_uncertain';b.operator_events.push({id:uuid(),status:'print_uncertain',note:'デモ：印刷結果を確認するまで再印刷しない例',created:new Date().toISOString()});
function parseRows(text){let rows=[],row=[],value='',quoted=false,closed=false;for(let i=0;i<text.length;i++){const c=text[i];if(quoted){if(c==='"'){if(text[i+1]==='"'){value+='"';i++;}else{quoted=false;closed=true;}}else value+=c;continue;}if(c==='"'&&!value&&!closed){quoted=true;continue;}if(c===','){row.push(value);value='';closed=false;continue;}if(c==='\r'||c==='\n'){if(c==='\r'&&text[i+1]==='\n')i++;row.push(value);rows.push(row);row=[];value='';closed=false;continue;}if(closed)throw Error('CSVの引用符を確認してください。');value+=c;}if(quoted)throw Error('CSVの引用符を確認してください。');if(value||row.length||closed){row.push(value);rows.push(row);}return rows;}
async function request(path,options={}){
 const u=new URL(path,location.origin),parts=u.pathname.split('/').filter(Boolean),method=options.method||'GET';let body=typeof options.body==='string'?JSON.parse(options.body):options.body;
 if(u.pathname==='/v1/printer')return {queue:'PDF',status:'idle',automatic_printing:false,job_to_batch_link:false,printing_verified:false};
 if(u.pathname==='/v1/preview')return preview(body);
 if(u.pathname==='/v1/import-preview'){
  if(body.byteLength>1048576)throw Error('CSVは1 MiB以内です。');let text;try{text=new TextDecoder('utf-8',{fatal:true}).decode(body);}catch{text=new TextDecoder('shift-jis',{fatal:true}).decode(body);}const rows=parseRows(text.replace(/^\uFEFF/,''));const batch=contentFromRows(rows);if(!rows.length||rows.length>100||rows.some(r=>r.length!==99)||JSON.stringify(rowsFor(batch))!==JSON.stringify(rows))throw Error('Upriの99列・ヘッダーなしCSVを使用してください。');return {batch,preview:preview(batch),saved:false};
 }
 const map=parts[1]==='drafts'?drafts:parts[1]==='batches'?batches:null;if(!map)throw Error('この操作はデモにはありません。');
 if(parts.length===2){if(method==='POST')return clone(newDraft(body));const items=Array.from(map.values()).reverse(),offset=Number(u.searchParams.get('offset')||0),limit=Number(u.searchParams.get('limit')||30);return clone({items:items.slice(offset,offset+limit),total:items.length});}
 const obj=map.get(parts[2]);if(!obj)throw Error('デモデータが見つかりません。');
 if(parts[1]==='drafts'){if(method==='PUT'){if(obj.prepared_batch||obj.revision!==body.revision)throw Error('下書きを再読込してください。');obj.batch=clone(body.batch);obj.revision++;obj.updated=new Date().toISOString();}if(parts[3]==='prepare')return clone(prepare(obj));return clone(obj);}
 if(parts[3]==='preview')return preview(obj.batch);
 if(parts[3]==='csv')return new Blob(['\uFEFF'+csvText(rowsFor(obj.batch))],{type:'text/csv;charset=utf-8'});
 if(parts[3]==='events'){if(!obj.operator_events.some(e=>e.id===body.event_id))obj.operator_events.push({id:body.event_id,status:body.status,note:body.note,created:new Date().toISOString()});obj.operator_status=body.status;}
 if(parts[3]==='history'){obj.shipments.forEach((s,i)=>s.tracking=`DEMO-TRACK-${i+1}`);obj.state='history_received';}
 return clone(obj);
}
return {request,firstId:first.id};
};
