// Spotify API credentials
const clientId = 'ee31a7f71f474295a798c8180dd03be3'; // Replace with your Client ID
const clientSecret = 'd8f98f46ae934b0fa306fbed2f70fb4c'; // Replace with your Client Secret

// Spotify API endpoints
const tokenEndpoint = 'https://accounts.spotify.com/api/token';
const apiEndpoint = 'https://api.spotify.com/v1';

// Get an access token from Spotify
async function getAccessToken() {
  const response = await fetch(tokenEndpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'Authorization': 'Basic ' + btoa(`${clientId}:${clientSecret}`),
    },
    body: new URLSearchParams({
      grant_type: 'client_credentials',
    }),
  });

  const data = await response.json();
  return data.access_token;
}

// Search for tracks, albums, or artists
async function searchSpotify(query) {
  const accessToken = await getAccessToken();
  const response = await fetch(`${apiEndpoint}/search?q=${encodeURIComponent(query)}&type=track,album,artist`, {
    headers: {
      'Authorization': `Bearer ${accessToken}`,
    },
  });

  const data = await response.json();
  return data;
}

// Display search results
function displayResults(results) {
  const resultsContainer = document.getElementById('results');
  resultsContainer.innerHTML = '';

  if (results.tracks.items.length === 0) {
    resultsContainer.innerHTML = '<p>No results found.</p>';
    return;
  }

  results.tracks.items.forEach(track => {
    const trackElement = document.createElement('div');
    trackElement.className = 'track';

    trackElement.innerHTML = `
      <img src="${track.album.images[0].url}" alt="${track.name}">
      <div class="track-info">
        <div class="track-name">${track.name}</div>
        <div class="track-artist">${track.artists.map(artist => artist.name).join(', ')}</div>
      </div>
    `;

    resultsContainer.appendChild(trackElement);
  });
}

// Handle search button click
document.getElementById('search-button').addEventListener('click', async () => {
  const query = document.getElementById('search-input').value;
  if (query) {
    const results = await searchSpotify(query);
    displayResults(results);
  }
});