/* TourInsight 3.5 — practical discovery tools: compare, budget fit and independent review checks. */
(() => {
  const $ = (s, r=document) => r.querySelector(s);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const selected = new Set();
  const fieldData = () => window.TourInsightFieldGuideData || null;
  const compareDock = $('#fg-compare-dock');
  const compareModal = $('#fg-compare-modal');
  const priceValue = value => {
    const match = String(value || '').replace(/,/g,'').match(/\d+(?:\.\d+)?/);
    return match ? Number(match[0]) : null;
  };
  const allItems = () => {
    const data = fieldData();
    return data ? [...data.stays, ...data.activities] : [];
  };
  const sourceFor = item => {
    const data = fieldData();
    return data?.sources?.[item.source] || {};
  };
  function refreshDock(){
    if(!compareDock) return;
    const count = selected.size;
    compareDock.hidden = count === 0;
    compareDock.innerHTML = `<span><b>${count}</b> ${count===1?'place':'places'} selected</span><span class="fg-compare-hint">Compare location, cost evidence, traveller notes and booking checks.</span><div><button class="button button-primary" id="fg-compare-open" ${count<2?'disabled':''}>Compare ${count || ''} →</button><button class="fg-clear-compare" id="fg-compare-clear">Clear</button></div>`;
  }
  function compareTable(){
    const items = allItems().filter(x=>selected.has(x.id)).slice(0,3);
    if(!items.length) return;
    const rows = [
      ['Type', x=>x.type || x.time || 'Not stated'],
      ['Area', x=>x.place || 'Not stated'],
      ['Price evidence', x=>x.price || x.cost || 'Not stated'],
      ['Traveller signal', x=>x.signal || 'Not stated'],
      ['What to consider', x=>x.note || 'No additional note'],
      ['Source date', x=>sourceFor(x).date || 'Not stated'],
    ];
    const head = `<thead><tr><th scope="col">Compare</th>${items.map(x=>`<th scope="col"><b>${esc(x.name)}</b><small>${esc(x.dest)}</small><button data-fg-remove-compare="${esc(x.id)}">Remove</button></th>`).join('')}</tr></thead>`;
    const body = rows.map(([label,fn])=>`<tr><th scope="row">${esc(label)}</th>${items.map(x=>`<td>${esc(fn(x))}</td>`).join('')}</tr>`).join('');
    const checks = `<tr><th scope="row">Independent checks</th>${items.map(x=>`<td class="fg-check-links"><a target="_blank" rel="noopener" href="https://www.google.com/search?q=${encodeURIComponent(x.name+' recent reviews')}">Recent reviews ↗</a><a target="_blank" rel="noopener" href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(x.query || x.name)}">Map & location ↗</a><a target="_blank" rel="noopener" href="https://www.tripadvisor.in/Search?q=${encodeURIComponent(x.name)}">Tripadvisor search ↗</a></td>`).join('')}</tr>`;
    const evidence = `<tr><th scope="row">Original evidence</th>${items.map(x=>`<td><a target="_blank" rel="noopener" href="${esc(sourceFor(x).url || '#')}">Read source ↗</a></td>`).join('')}</tr>`;
    $('#fg-compare-body').innerHTML = `<div class="fg-compare-table-wrap"><table class="fg-compare-table">${head}<tbody>${body}${checks}${evidence}</tbody></table></div><p class="fg-compare-disclaimer">No composite score or star rating is calculated. Check current guest reviews, exact property identity, total price, policies and availability independently. Reported prices may refer to different units (per person, per night or full trip), so compare like with like.</p>`;
    compareModal.hidden = false;
    document.body.classList.add('fg-modal-open');
  }
  document.addEventListener('click', e=>{
    const compare = e.target.closest('[data-fg-compare]');
    if(compare){
      const id=compare.dataset.fgCompare;
      if(selected.has(id)) selected.delete(id); else if(selected.size<3) selected.add(id);
      document.querySelectorAll(`[data-fg-compare="${CSS.escape(id)}"]`).forEach(b=>{b.classList.toggle('is-selected',selected.has(id));b.textContent=selected.has(id)?'✓ Added':'＋ Compare';});
      refreshDock(); return;
    }
    if(e.target.closest('#fg-compare-open')){if(selected.size>=2)compareTable();return;}
    if(e.target.closest('#fg-compare-clear')){selected.clear();document.querySelectorAll('[data-fg-compare]').forEach(b=>{b.classList.remove('is-selected');b.textContent='＋ Compare';});refreshDock();return;}
    if(e.target.closest('[data-fg-close]')){compareModal.hidden=true;document.body.classList.remove('fg-modal-open');return;}
    const remove=e.target.closest('[data-fg-remove-compare]');
    if(remove){selected.delete(remove.dataset.fgRemoveCompare);refreshDock();if(selected.size<2){compareModal.hidden=true;document.body.classList.remove('fg-modal-open');}else compareTable();document.querySelectorAll(`[data-fg-compare="${CSS.escape(remove.dataset.fgRemoveCompare)}"]`).forEach(b=>{b.classList.remove('is-selected');b.textContent='＋ Compare';});}
  });
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&compareModal&&!compareModal.hidden){compareModal.hidden=true;document.body.classList.remove('fg-modal-open');}});
  const budget = $('#fg-budget');
  budget?.addEventListener('input',()=>{
    const ceiling=Number(budget.value);
    document.querySelectorAll('.fg-card').forEach(card=>{
      const amount=priceValue(card.dataset.price);
      card.hidden=!!(ceiling>0 && amount!==null && amount>ceiling);
    });
  });
  // Expose a tiny integration hook for the existing Field Guide renderer without replacing its data source.
  window.TourInsightDiscovery = {refreshDock, selected};
})();
