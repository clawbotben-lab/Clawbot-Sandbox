let chart;

async function run() {
  const isrc = document.getElementById('isrc').value.trim();
  const days = document.getElementById('days').value || '14';
  const status = document.getElementById('status');
  const meta = document.getElementById('meta');

  if (!isrc) {
    status.textContent = 'Please enter an ISRC';
    return;
  }

  status.textContent = 'Loading...';
  meta.textContent = '';

  try {
    const res = await fetch(`/api/overlay?isrc=${encodeURIComponent(isrc)}&days=${encodeURIComponent(days)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Request failed');

    if (chart) chart.destroy();
    const ctx = document.getElementById('chart');
    chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: data.labels,
        datasets: [
          {
            label: 'Spotify Streams',
            data: data.spotify_streams,
            borderColor: '#1DB954',
            backgroundColor: 'rgba(29,185,84,0.1)',
            tension: 0.25,
          },
          {
            label: 'TikTok Creations',
            data: data.tiktok_creations,
            borderColor: '#111',
            backgroundColor: 'rgba(0,0,0,0.1)',
            tension: 0.25,
          },
        ],
      },
      options: {
        responsive: true,
        interaction: { mode: 'index', intersect: false },
        plugins: { legend: { position: 'top' } },
      },
    });

    status.textContent = `Loaded track_id ${data.track_id}`;
    meta.textContent = JSON.stringify(data.raw, null, 2);
  } catch (e) {
    status.textContent = `Error: ${e.message}`;
  }
}

document.getElementById('run').addEventListener('click', run);
