'use strict';

// Isolated Chrome integration checks. Firebase/API responses are test doubles;
// no credentials are submitted and no persisted backend circuits are modified.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { spawn } = require('node:child_process');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const base = process.env.BROWSER_TEST_URL || 'http://127.0.0.1:3000';
const output = path.resolve(process.argv[2] || path.join(root, 'backend/tests/artifacts/phase_10/browser'));
const chromePath = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const report = { mode: 'Real Chrome; isolated Firebase session and mocked API transport', checks: [], errors: [], requests: [] };
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'spicecraft-browser-'));
let chrome, socket, serial = 0;
const pending = new Map();
let exportMode = 'routing', saveMode = 'fail', listMode = 'ok';
let projectCreateMode = 'fail', sourceCreateMode = 'fail', sourceDeleteMode = 'fail';
let createdProject = null, createdSource = null;
let circuit = { ...JSON.parse(fs.readFileSync(path.join(root, 'backend/circuits/rc_low_pass_filter.json'), 'utf8')), id: 'browser-circuit' };
const project = { id: 'browser-project', name: 'Browser project', description: 'Isolated browser verification', firebase_uid: 'browser-user', created_at: '2026-01-01T00:00:00Z' };
const source = { id: 'browser-source', project_id: project.id, title: 'Browser source', source_name: 'Fixture', source_url: null, image_url: null, created_at: project.created_at };
function send(method, params = {}) {
  const id = ++serial;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 60000);
    pending.set(id, { resolve, reject, timer });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text + ': ' + (result.exceptionDetails.exception?.description || ''));
  return result.result.value;
}
async function wait(expression, timeout = 60000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    if (await evaluate(expression)) return;
    await delay(100);
  }
  throw new Error(`Browser assertion timed out: ${expression}; URL: ${await evaluate('location.href')}; page: ${await evaluate('document.body.innerText.slice(0, 2500)')}`);
}
const hasText = text => `document.body.innerText.includes(${JSON.stringify(text)})`;
async function check(name, expression) {
  await wait(expression);
  report.checks.push({ name, status: 'PASS' });
}
async function click(text, tag = 'button') {
  const selector = `[...document.querySelectorAll(${JSON.stringify(tag)})].find(e => e.textContent.trim() === ${JSON.stringify(text)})`;
  await wait(`Boolean(${selector}) && !(${selector}).disabled`);
  await evaluate(`(${selector}).click()`);
}
async function navigate(route) {
  await send('Page.navigate', { url: base + route });
  await wait(`location.pathname === ${JSON.stringify(route)} && document.readyState === 'complete'`);
}
async function screenshot(name) {
  const image = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  fs.writeFileSync(path.join(output, name + '.png'), Buffer.from(image.data, 'base64'));
}
async function intercept(event) {
  const { requestId, request } = event;
  const url = new URL(request.url);
  const fulfill = (status, body, type = 'application/json') => send('Fetch.fulfillRequest', {
    requestId, responseCode: status, responseHeaders: [
      { name: 'Content-Type', value: type }, { name: 'Access-Control-Allow-Origin', value: base },
      { name: 'Access-Control-Allow-Headers', value: 'authorization,content-type' },
      { name: 'Access-Control-Allow-Methods', value: 'GET,PUT,POST,DELETE,OPTIONS' },
    ], body: Buffer.from(typeof body === 'string' ? body : JSON.stringify(body)).toString('base64'),
  });
  if (url.origin === base) return send('Fetch.continueRequest', { requestId });
  if (url.hostname === 'localhost' || url.hostname === '127.0.0.1') {
    if (request.method === 'OPTIONS') return fulfill(204, '');
    report.requests.push({ method: request.method, path: url.pathname });
    if (url.pathname === '/circuits') return listMode === 'error'
      ? fulfill(503, { detail: { message: 'Circuit library temporarily unavailable', stage: 'load', retryable: true } })
      : fulfill(200, listMode === 'empty' ? [] : [circuit]);
    if (url.pathname === '/circuits/missing') return fulfill(404, { detail: 'Circuit not found' });
    if (url.pathname === '/circuits/unsupported') return fulfill(200, { ...circuit, id: 'unsupported', components: [{ id: 'U1', reference: 'U1', type: 'LM358', value: 'LM358' }], wires: [] });
    if (url.pathname.endsWith('/export/asc')) {
      if (exportMode === 'success') return fulfill(200, 'Version 4\nSHEET 1 880 680\n', 'application/octet-stream');
      if (exportMode === 'invalid-success') return fulfill(200, '<html>Gateway sign-in page</html>', 'text/html');
      if (exportMode === 'offline') return send('Fetch.failRequest', { requestId, errorReason: 'InternetDisconnected' });
      if (exportMode === 'malformed') return fulfill(502, '<html>gateway failed</html>', 'text/html');
      const timeout = exportMode === 'timeout';
      return fulfill(timeout ? 504 : 422, { detail: { message: 'Circuit processing failed', stage: exportMode === 'unsupported' ? 'input_validation' : 'routing', retryable: timeout,
        diagnostics: [{ message: timeout ? 'Routing exceeded its execution budget' : exportMode === 'unsupported' ? 'Component LM358 is not currently supported by SpiceCraft' : 'No valid collision-free route found', code: timeout ? 'PIPELINE_TIMEOUT' : exportMode === 'unsupported' ? 'UNSUPPORTED_COMPONENT' : 'ROUTING_FAILED', component: 'R1', pin: '1', net: 'N7', stage: exportMode === 'unsupported' ? 'input_validation' : 'routing' }] } });
    }
    if (url.pathname === '/circuits/browser-circuit') {
      if (request.method === 'PUT') {
        if (saveMode === 'fail') return fulfill(422, { detail: { message: 'Circuit validation failed', stage: 'input_validation', diagnostics: [{ message: 'Passive value must be numeric', component: 'R1', code: 'INVALID_VALUE' }] } });
        circuit = JSON.parse(request.postData);
      }
      return fulfill(200, circuit);
    }
    if (url.pathname === '/projects') {
      if (request.method === 'POST') {
        if (projectCreateMode === 'fail') return fulfill(503, { detail: { message: 'Project save temporarily unavailable', retryable: true } });
        createdProject = { ...project, ...JSON.parse(request.postData), id: 'created-project' };
        return fulfill(201, createdProject);
      }
      return fulfill(200, [project, ...(createdProject ? [createdProject] : [])]);
    }
    if (url.pathname === '/projects/browser-project') return fulfill(200, project);
    if (url.pathname === '/projects/browser-project/sources') {
      if (request.method === 'POST') {
        if (sourceCreateMode === 'fail') return fulfill(503, { detail: { message: 'Source save temporarily unavailable', retryable: true } });
        createdSource = { ...source, ...JSON.parse(request.postData), id: 'created-source' };
        return fulfill(201, createdSource);
      }
      return fulfill(200, [source, ...(createdSource ? [createdSource] : [])]);
    }
    if (url.pathname === '/sources/created-source' && request.method === 'DELETE') {
      if (sourceDeleteMode === 'fail') return fulfill(503, { detail: 'Source delete temporarily unavailable' });
      createdSource = null;
      return fulfill(204, '');
    }
    return fulfill(404, { detail: 'Unknown browser test API route' });
  }
  // External Firebase/analytics calls never leave the isolated test browser.
  if (url.hostname === 'identitytoolkit.googleapis.com' && url.pathname.endsWith(':lookup')) {
    return fulfill(200, { users: [{ localId: 'browser-user', displayName: 'Browser Test', email: 'browser@example.invalid', emailVerified: true, providerUserInfo: [] }] });
  }
  return fulfill(200, {});
}
async function main() {
  fs.mkdirSync(output, { recursive: true });
  chrome = spawn(chromePath, ['--headless=new', '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
  const portFile = path.join(profile, 'DevToolsActivePort');
  for (let i = 0; !fs.existsSync(portFile) && i < 150; i++) await delay(100);
  const port = fs.readFileSync(portFile, 'utf8').split('\n')[0];
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  socket = new WebSocket(targets.find(target => target.type === 'page').webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  socket.onmessage = message => {
    const data = JSON.parse(message.data);
    if (data.id) {
      const call = pending.get(data.id);
      if (!call) return;
      clearTimeout(call.timer); pending.delete(data.id);
      data.error ? call.reject(new Error(JSON.stringify(data.error))) : call.resolve(data.result);
    } else if (data.method === 'Fetch.requestPaused') intercept(data.params).catch(error => report.errors.push(error.message));
    else if (data.method === 'Runtime.exceptionThrown') report.errors.push(data.params.exceptionDetails.exception?.description || data.params.exceptionDetails.text);
  };
  await send('Page.enable'); await send('Runtime.enable');
  await send('Fetch.enable', { patterns: [{ urlPattern: '*' }] });
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await send('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: output });
  await navigate('/login');
  await wait('Array.isArray(window.webpackChunk_N_E)');
  await evaluate(`new Promise((resolve, reject) => window.webpackChunk_N_E.push([['browser-auth-ready'], {}, require => { try { require('(app-pages-browser)/./lib/firebase.ts').auth.authStateReady().then(() => resolve(true), reject); } catch (error) { reject(error); } }]))`);
  const env = fs.readFileSync(path.join(root, 'frontend/.env.local'), 'utf8');
  const apiKey = env.match(/^NEXT_PUBLIC_FIREBASE_API_KEY\s*=\s*["']?([^\s"']+)/m)?.[1];
  assert(apiKey, 'Local Firebase public API configuration required');
  const now = Math.floor(Date.now() / 1000);
  const token = [Buffer.from('{"alg":"none"}').toString('base64url'), Buffer.from(JSON.stringify({ sub: 'browser-user', user_id: 'browser-user', iat: now, exp: now + 3600, auth_time: now })).toString('base64url'), 'test'].join('.');
  const user = { uid: 'browser-user', email: 'browser@example.invalid', emailVerified: true, isAnonymous: false, displayName: 'Browser Test', providerData: [], stsTokenManager: { refreshToken: 'isolated-test', accessToken: token, expirationTime: Date.now() + 3600000 }, createdAt: String(Date.now()), lastLoginAt: String(Date.now()), apiKey, appName: '[DEFAULT]' };
  await evaluate(`new Promise((resolve,reject) => { const request = indexedDB.open('firebaseLocalStorageDb',1); request.onupgradeneeded = () => request.result.createObjectStore('firebaseLocalStorage',{keyPath:'fbase_key'}); request.onerror = () => reject(request.error); request.onsuccess = () => { const db=request.result; const tx=db.transaction('firebaseLocalStorage','readwrite'); tx.objectStore('firebaseLocalStorage').put({fbase_key:${JSON.stringify(`firebase:authUser:${apiKey}:[DEFAULT]`)},value:${JSON.stringify(user)}}); tx.oncomplete=()=>{db.close();resolve(true)}; tx.onerror=()=>reject(tx.error); }; })`);
  await navigate('/search');
  await check('Circuit library loads authenticated test session', hasText(circuit.name));
  await click('View Circuit', 'a');
  await check('Library navigates to editor', hasText('All Changes Saved'));
  await click('Export LTspice (.asc)');
  await check('Routing failure includes net, component and pin', `${hasText('No valid collision-free route found')} && ${hasText('Net: N7')} && ${hasText('Pin: 1')}`);
  await screenshot('desktop-routing-error');
  for (const [mode, expected] of [['unsupported', 'LM358'], ['timeout', 'Routing exceeded'], ['malformed', 'HTTP 502'], ['offline', 'Unable to reach the API'], ['invalid-success', 'invalid ASC download']]) {
    exportMode = mode;
    await click('Retry export');
    await check(`${mode} export remains retryable with useful diagnostics`, hasText(expected));
  }
  await evaluate(`(() => {const input=document.querySelector('[aria-label="Component value for R1"]'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'22k'); input.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await check('Editing preserves draft and blocks export', `${hasText('Unsaved Changes')} && [...document.querySelectorAll('button')].some(e=>e.textContent.trim()==='Retry export' && e.disabled)`);
  await click('Save Changes');
  await check('Failed save keeps input and enables retry', `${hasText('Circuit validation failed')} && document.querySelector('[aria-label="Component value for R1"]').value === '22k' && ${hasText('Retry save')}`);
  await screenshot('desktop-save-error');
  saveMode = 'success';
  await click('Retry save');
  await check('Successful retry saves preserved draft', hasText('All Changes Saved'));
  exportMode = 'success';
  await click('Retry export');
  await check('Export retry downloads file', hasText('Downloaded!'));
  await wait(`[...document.querySelectorAll('button')].some(e => e.textContent.trim() === 'Export LTspice (.asc)' && !e.disabled)`);
  await click('Back to Search', 'a');
  await check('Back navigation returns to library', hasText('Browse the circuit library'));
  await click('View Circuit', 'a');
  await check('Reloaded circuit retains saved value', `document.querySelector('[aria-label="Component value for R1"]')?.value === '22k'`);
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  exportMode = 'routing';
  await click('Export LTspice (.asc)');
  await check('Mobile error and retry visible', hasText('No valid collision-free route found'));
  await screenshot('mobile-routing-error');
  await check('Mobile page has no horizontal document overflow', 'document.documentElement.scrollWidth <= innerWidth + 1');
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await navigate('/circuits/unsupported');
  await check('Unsupported source suppresses schematic rather than substituting a component', `${hasText("Unknown component type 'LM358'")} && document.querySelectorAll('.react-flow__node').length === 0`);
  await navigate('/circuits/missing');
  await check('Missing route displays not-found state', hasText('Circuit Not Found'));
  listMode = 'error'; await navigate('/search');
  await check('Shared API library failure is readable', hasText('Circuit library temporarily unavailable'));
  listMode = 'empty'; await click('Try Again');
  await check('Library retry supports empty state', hasText('No circuits'));
  listMode = 'ok'; await navigate('/dashboard');
  await check('Shared API dashboard projects still load', hasText(project.name));
  await click('New Project', 'button[aria-haspopup="dialog"]');
  await wait('document.querySelector("#project-name") !== null');
  await evaluate(`(() => {const input=document.querySelector('#project-name'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'Preserved project draft'); input.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await click('Create Project');
  await check('Failed project creation preserves form input', `${hasText('Project save temporarily unavailable')} && document.querySelector('#project-name')?.value === 'Preserved project draft'`);
  projectCreateMode = 'success';
  await click('Create Project');
  await check('Explicit project retry adds the saved project', `${hasText('Preserved project draft')} && !document.querySelector('#project-name')`);
  await navigate('/projects/browser-project');
  await check('Shared API project and source data still load', `${hasText(project.name)} && ${hasText(source.title)}`);
  await click('Add Source');
  await wait('document.querySelector("#source-title") !== null');
  await evaluate(`(() => {const input=document.querySelector('#source-title'); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'Preserved source draft'); input.dispatchEvent(new Event('input',{bubbles:true})); document.querySelector('[role="dialog"] button[type="submit"]').click();})()`);
  await check('Failed source creation preserves form input', `${hasText('Source save temporarily unavailable')} && document.querySelector('#source-title')?.value === 'Preserved source draft'`);
  sourceCreateMode = 'success';
  await evaluate(`document.querySelector('[role="dialog"] button[type="submit"]').click()`);
  await check('Explicit source retry adds the saved source', `${hasText('Preserved source draft')} && !document.querySelector('#source-title')`);
  await evaluate('window.confirm = () => true');
  await evaluate(`document.querySelector('[aria-label="Delete source"]').click()`);
  await check('Failed source deletion retains row and permits retry', `${hasText('Source delete temporarily unavailable')} && ${hasText('Preserved source draft')} && !document.querySelector('[aria-label="Delete source"]').disabled`);
  sourceDeleteMode = 'success';
  await evaluate(`document.querySelector('[aria-label="Delete source"]').click()`);
  await check('Explicit source delete retry removes only the saved row', `!${hasText('Preserved source draft')} && ${hasText(source.title)}`);
  for (const route of ['/editor', '/exports', '/favorites', '/assistant']) {
    await navigate(route);
    await check(`Surrounding route ${route} remains accessible`, 'document.querySelector("main") !== null');
  }
  await screenshot('shared-project-routes');
  assert(fs.readdirSync(output).some(name => name.endsWith('.asc')), 'Browser must save the successful download');
  report.checks.push({ name: 'Successful download exists on disk (mock ASC transport)', status: 'PASS' });
  assert.equal(report.errors.length, 0, JSON.stringify(report.errors));
  report.status = 'PASS';
}
main().catch(error => { report.status = 'FAIL'; report.failure = error.stack; process.exitCode = 1; }).finally(async () => {
  if (socket?.readyState === WebSocket.OPEN) {
    try { await screenshot('final-state'); await send('Browser.close'); } catch {}
    socket.close();
  }
  chrome?.kill();
  for (const call of pending.values()) clearTimeout(call.timer);
  fs.mkdirSync(output, { recursive: true });
  fs.writeFileSync(path.join(output, 'browser_report.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ status: report.status, checks: report.checks.length, failure: report.failure, report: path.join(output, 'browser_report.json') }, null, 2));
  try { fs.rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch {}
});
