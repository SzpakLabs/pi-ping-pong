import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';

// No prompt()/stream(), HTTP, credentials or model response in this native profile probe.
const source = path.resolve(import.meta.dirname, '..');
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ppp-goal-profile-'));
const lab = path.join(root, 'Test-lab');
const release = '/Users/macos/.pi/agent/install/releases/1.3.0';
const goal = '/Users/macos/.pi/agent/npm/node_modules/@narumitw/pi-goal/dist/index.ts';
let session;
try {
  const prepared = spawnSync('python3', ['-B', path.join(source, 'scripts/prepare_goal_smoke.py'), '--lab', lab], { encoding: 'utf8' });
  assert.equal(prepared.status, 0, prepared.stderr);
  const home = path.join(lab, 'Test-home');
  const cwd = path.join(lab, 'Test-project');
  const agentDir = path.join(home, '.pi/agent');
  process.env = { PATH: process.env.PATH, HOME: home, PI_CODING_AGENT_DIR: agentDir, PI_OFFLINE: '1' };
  globalThis.fetch = () => { throw new Error('Test no-network profile probe'); };
  const sdk = await import(pathToFileURL(path.join(release, 'node_modules/@earendil-works/pi-coding-agent/dist/index.js')).href);
  const settingsManager = sdk.SettingsManager.create(cwd, agentDir);
  assert.deepEqual(settingsManager.getDefaultTools(), ['read', 'write']);
  const resourceLoader = new sdk.DefaultResourceLoader({ cwd, agentDir, settingsManager, noExtensions: true, additionalExtensionPaths: [goal], noSkills: true, noPromptTemplates: true, noContextFiles: true });
  await resourceLoader.reload();
  assert.deepEqual(resourceLoader.getExtensions().errors, []);
  ({ session } = await sdk.createAgentSession({ cwd, agentDir, settingsManager, resourceLoader, sessionManager: sdk.SessionManager.inMemory() }));
  const active = session.getActiveToolNames().sort();
  assert.deepEqual(active, ['goal_blocked', 'goal_complete', 'goal_wait', 'read', 'write']);
  assert.equal(session.messages.length, 0);
  assert.deepEqual(JSON.parse(fs.readFileSync(path.join(agentDir, 'auth.json'), 'utf8')), {});
  console.log('Native Goal profile PASS: actual Goal extension + read/write, no bash/codemode/MCP, zero messages/model calls');
} finally {
  session?.dispose();
  fs.rmSync(root, { recursive: true, force: true });
}
