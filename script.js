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
  const body = `Name: ${name}\nEmail: ${email}\n\nRequirements:\n${message}`;
  window.location.href = buildMailto('Website Product Inquiry', body);
});

document.getElementById('contactForm').addEventListener('submit', function(e) {
  e.preventDefault();
  const body =
`Name: ${document.getElementById('name').value || ''}
Email: ${document.getElementById('email').value || ''}
Company: ${document.getElementById('company').value || ''}
Country: ${document.getElementById('country').value || ''}
Product: ${document.getElementById('product').value || ''}

Requirements:
${document.getElementById('message').value || ''}`;
  window.location.href = buildMailto('Business Inquiry from Website', body);
});
