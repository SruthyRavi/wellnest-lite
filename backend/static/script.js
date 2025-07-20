document.getElementById('moodForm').addEventListener('submit', function(e) {
  e.preventDefault();
  const journal = document.querySelector('textarea[name="journal"]').value;

  fetch('/predict', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ text: journal })
  })
  .then(res => res.json())
  .then(data => {
    document.getElementById('result').innerHTML = `
      <h3>Detected Mood: ${data.mood}</h3>
      <p><b>Suggestion:</b> ${data.suggestion}</p>
    `;
    loadHistory(); // Refresh history
  });
});

// Load journal history
function loadHistory() {
  fetch('/history')
    .then(res => res.json())
    .then(data => {
      const container = document.getElementById('history');
      container.innerHTML = '';
      data.entries.forEach(entry => {
        const div = document.createElement('div');
        div.innerHTML = `<p><b>${entry.date}</b> - Mood: ${entry.mood}<br>${entry.text}</p><hr>`;
        container.appendChild(div);
      });
    });
}

loadHistory(); // Load on page load
const div = document.createElement('div');
div.className = 'entry';
div.innerHTML = `...`;
document.getElementById('history').appendChild(div);
