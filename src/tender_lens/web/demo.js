async function refreshIndex(){try{const r=await fetch('/api/demo/status');const d=await r.json();document.getElementById('index-state').textContent=`${d.documents.length} документа · ${d.chunks} чанков\nИсточник: ${d.source}\nИзмерено: ${d.at}\n\n`+d.documents.map(x=>`${x.status.toUpperCase()}  ${x.title}`).join('\n')}catch(e){document.getElementById('index-state').textContent='Состояние индекса недоступно'}}
document.getElementById('refresh-index').onclick=refreshIndex;
document.getElementById('replay').onclick=async()=>{const el=document.getElementById('replay-state');const r=await fetch('/api/demo/replay',{method:'POST'});const d=await r.json();el.textContent=r.ok?`${d.queued} события · ${d.message}`:(d.error?.message||'Ошибка очереди');await refreshIndex()};
document.querySelectorAll('[data-query]').forEach(b=>b.onclick=()=>{document.getElementById('query').value=b.dataset.query;document.getElementById('query').focus()});
document.getElementById('demo-reset').onclick=()=>{sessionStorage.removeItem('tenderLensApiKey');location.reload()};
refreshIndex();
