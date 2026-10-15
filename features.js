(() => {
  const tools = document.querySelector('.feature-tools');
  const search = document.querySelector('#feature-search');
  const filter = document.querySelector('#feature-filter');
  const isEnglish = document.documentElement.lang === 'en';
  const sections = [...document.querySelectorAll('.feature-section')];
  const entries = sections.flatMap(section => [...section.querySelectorAll('.feature')].map(card => ({
    card, section, text: card.querySelector('h3').textContent.toLocaleLowerCase() + ' ' + card.querySelector('p').textContent.toLocaleLowerCase(),
    type: card.querySelector('.badge').textContent
  })));
  function update() {
    const words = search.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    let count = 0;
    for (const entry of entries) {
      entry.card.hidden = !words.every(word => entry.text.includes(word)) || Boolean(filter.value && filter.value !== entry.type);
      if (!entry.card.hidden) count++;
    }
    for (const section of sections) {
      section.hidden = !entries.some(entry => entry.section === section && !entry.card.hidden);
      document.querySelector(`.category-nav a[href="#${section.id}"]`).hidden = section.hidden;
    }
    document.querySelector('#feature-count').textContent = isEnglish
      ? `Showing ${count} of ${entries.length} features`
      : `显示 ${count} / ${entries.length} 项功能`;
    document.querySelector('#no-results').hidden = count !== 0;
  }
  search.addEventListener('input', update);
  filter.addEventListener('change', update);
  document.querySelector('#reset-filters').addEventListener('click', () => {
    search.value = '';
    filter.value = '';
    update();
    search.focus();
  });
  tools.hidden = false;
})();
