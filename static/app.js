const modal = document.querySelector('#modal');
const openModal = document.querySelector('#open-modal');
const closeModal = document.querySelector('#close-modal');
if (modal && openModal && closeModal) {
  openModal.onclick = () => modal.classList.add('open');
  closeModal.onclick = () => modal.classList.remove('open');
  modal.onclick = (event) => { if (event.target === modal) modal.classList.remove('open'); };
}

const topics = [...document.querySelectorAll('.topic')];
const searchInput = document.querySelector('#search');
const initialHashtag = new URLSearchParams(window.location.search).get('tag');
if (initialHashtag) searchInput.value = `#${initialHashtag.toLowerCase()}`;
const refresh = () => {
  const query = searchInput.value.toLowerCase();
  const activeCategory = document.querySelector('.category.selected').dataset.category;
  const activeTab = document.querySelector('.tab.active').dataset.tab;
  let visible = 0;
  topics.forEach((topic) => {
    const matchesText = topic.textContent.toLowerCase().includes(query);
    const matchesCategory = activeCategory === 'All topics' || topic.dataset.category === activeCategory;
    const matchesTab = activeTab === 'all' || topic.dataset.tag.toLowerCase() === activeTab;
    topic.hidden = !(matchesText && matchesCategory && matchesTab);
    if (matchesText && matchesCategory && matchesTab) visible++;
  });
  document.querySelector('#empty').hidden = visible > 0;
};

searchInput.oninput = refresh;
document.querySelectorAll('.category').forEach((item) => {
  item.onclick = () => {
    document.querySelector('.category.selected').classList.remove('selected');
    item.classList.add('selected');
    refresh();
  };
});
document.querySelectorAll('.tab').forEach((item) => {
  item.onclick = () => {
    document.querySelector('.tab.active').classList.remove('active');
    item.classList.add('active');
    refresh();
  };
});

refresh();
