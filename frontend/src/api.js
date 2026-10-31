const API_BASE = window.__TTS_API_BASE__ || 'http://127.0.0.1:8771';
async function request(path, options) {
  const response = await fetch(API_BASE + path, options);
  const data = response.status === 204 ? null : await response.json();
  if (!response.ok) throw new Error((data && data.error) || '请求失败，请稍后重试。');
  return data;
}
function post(path, body) {
  return request(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
}
export const api = {
  config: () => request('/api/v1/config'),
  listBatches: () => request('/api/v1/batches'),
  batch: id => request('/api/v1/batches/' + encodeURIComponent(id)),
  createBatch: body => post('/api/v1/batches', body),
  stopBatch: id => post('/api/v1/batches/' + encodeURIComponent(id) + '/stop', {}),
  preview: body => post('/api/v1/preview', body),
  chooseDirectory: () => post('/api/v1/directory-picker', {}),
  audioURL: taskId => API_BASE + '/api/v1/tasks/' + encodeURIComponent(taskId) + '/audio'
};
