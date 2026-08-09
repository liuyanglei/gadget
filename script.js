const menuBtn = document.querySelector('.menu-btn');
const nav = document.querySelector('.nav');

menuBtn.addEventListener('click', () => nav.classList.toggle('open'));
document.querySelectorAll('.nav a').forEach(a => a.addEventListener('click', () => nav.classList.remove('open')));

function buildMailto(subject, body) {
  return `mailto:sales@example.com?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

document.getElementById('quickForm').addEventListener('submit', function(e) {
  e.preventDefault();
  const name = document.getElementById('qName').value || '';
  const email = document.getElementById('qEmail').value || '';
  const message = document.getElementById('qMessage').value || '';
  const body = `姓名：${name}\n邮箱：${email}\n\n需求：\n${message}`;
  window.location.href = buildMailto('网站产品询盘', body);
});

document.getElementById('contactForm').addEventListener('submit', function(e) {
  e.preventDefault();
  const body =
`姓名：${document.getElementById('name').value || ''}
邮箱：${document.getElementById('email').value || ''}
公司：${document.getElementById('company').value || ''}
国家/地区：${document.getElementById('country').value || ''}
产品：${document.getElementById('product').value || ''}

需求：
${document.getElementById('message').value || ''}`;
  window.location.href = buildMailto('网站商务询盘', body);
});
