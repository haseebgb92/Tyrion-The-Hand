// Read-only Node.js client for trusted local Advertpreneur applications.
// Works with Node 18+ and built-in fetch; no npm dependencies.
// Intentionally never logs the owner-only token.
'use strict';
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const secretPath = path.join(os.homedir(), 'Documents/Tyrion-The-Hand/data/knowledge-readonly.token');
async function searchKnowledge(query, {project = null, limit = 5, media = false} = {}) {
  if (typeof query !== 'string' || query.trim().length < 3) throw new Error('A meaningful query is required');
  const key = (await fs.readFile(secretPath, 'utf8')).trim();
  const res = await fetch('http://127.0.0.1:17877/api/knowledge/shared/'+(media?'media-search':'search'), {
    method: 'POST',
    headers: {'Content-Type':'application/json', 'X-Tyrion-Knowledge-Key':key},
    body: JSON.stringify({query, project, limit}),
    signal: AbortSignal.timeout(45000)
  });
  if (!res.ok) throw new Error('Tyrion knowledge retrieval failed: HTTP '+res.status);
  const data = await res.json();
  return data.result;
}
module.exports = {searchKnowledge};
