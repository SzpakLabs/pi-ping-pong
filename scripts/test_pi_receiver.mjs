import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

// Set this for nonstandard Pi layouts; dependency resolution needs jiti beside Pi.
const require = createRequire(process.env.PI_PACKAGE_JSON || path.join(os.homedir(), '.pi/agent/install/releases/1.3.0/node_modules/@earendil-works/pi-coding-agent/package.json'));
const { createJiti } = require('jiti');
const jiti = createJiti(import.meta.url);
const module = await jiti.import(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../extensions/pi-reviewed.ts'));
const extension = module.default ?? module;
const root = fs.mkdtempSync(path.join(os.tmpdir(), 'pi-receiver-test-'));
const write = (name, data) => fs.writeFileSync(path.join(root, name), JSON.stringify(data));
const get = name => JSON.parse(fs.readFileSync(path.join(root, name), 'utf8'));
const hooks = new Map(), commands = new Map(), messages = [], notices = [];
const entry = { type: 'custom', customType: 'pi-reviewed-run', data: { root, runId: 'Test-run', sessionId: 'Test-session' } };
const ctx = { model: { id: 'Sol', provider: 'Test' }, sessionManager: { getSessionId: () => 'Test-session', getEntries: () => [entry] }, ui: { notify: (...x) => notices.push(x) } };
const pi = { on: (name, handler) => hooks.set(name,handler), registerCommand: (name, command) => commands.set(name,command), sendMessage: (message, options) => messages.push({message,options}), appendEntry: () => {} };
extension(pi);
try {
  fs.mkdirSync(path.join(root,'pi-inbox'));
  write('config.json',{run_id:'Test-run',mode:'goal',review_transport:'pi',pi_session_id:'Test-session',review_model:'Sol',review_provider:'Test'});
  const envelope = { id:'one',run_id:'Test-run',session_id:'Test-session',kind:'review',message:'Codex checkpoint: read evidence',receipt:path.join(root,'receipt.txt') };
  write('pi-inbox/001.message.json',envelope);
  await hooks.get('session_start')({},ctx);
  assert.equal(messages.length,1);
  assert.equal(messages[0].options.deliverAs,'followUp');
  assert.equal(messages[0].options.triggerTurn,true);
  assert.equal(get('pi-inbox/001.delivery.json').status,'enqueued_in_pi');
  await hooks.get('session_shutdown')();
  await hooks.get('session_start')({},ctx);
  assert.equal(messages.length,1,'reload must not duplicate delivery');
  ctx.model.id='Luna';
  write('pi-inbox/002.message.json',{...envelope,id:'two'});
  await hooks.get('model_select')({},ctx);
  assert.equal(messages.length,1,'model mismatch must hold queue');
  assert.ok(notices.some(x=>x[0].includes('select Sol')));
  ctx.model.id='Sol';
  await hooks.get('model_select')({},ctx);
  assert.equal(messages.length,2);
  write('pi-inbox/003.message.json',{...envelope,id:'three',session_id:'other'});
  await hooks.get('model_select')({},ctx);
  assert.equal(messages.length,2,'wrong session must not receive message');
  assert.equal(get('pi-inbox/003.delivery.json').status,'rejected_identity');
  await hooks.get('session_shutdown')();
  const other={...ctx,sessionManager:{getSessionId:()=> 'different',getEntries:()=>[entry]}};
  await hooks.get('session_start')({},other);
  write('pi-inbox/004.message.json',{...envelope,id:'four'});
  await hooks.get('model_select')({},other);
  assert.equal(messages.length,2,'session switch must not inherit subscriptions');
  assert.ok(commands.has('pi-ping-pong') && commands.has('reviewed-run') && commands.has('reviewed-status'));
  assert.strictEqual(commands.get('pi-ping-pong').handler, commands.get('reviewed-run').handler, 'launcher alias must share the exact handler');
  const start = path.join(root, 'config.json');
  for (const name of ['pi-ping-pong', 'reviewed-run']) {
    ctx.model.id='Luna';
    await assert.rejects(commands.get(name).handler(start,ctx), /Select reviewer model Sol/);
    ctx.model.id='Sol';
    write('launch-attempt.json',{session_id:'Test-session'});
    await assert.rejects(commands.get(name).handler(start,ctx), /already launched/);
    fs.unlinkSync(path.join(root,'launch-attempt.json'));
  }
  assert.equal(get('pi-inbox/003.delivery.json').status,'rejected_identity','identity refusal remains active');
  console.log('Pi receiver: launcher alias parity, duplicate refusal, model/identity checks, delivery, reload and session switch passed.');
} finally {
  await hooks.get('session_shutdown')();
  fs.rmSync(root,{recursive:true,force:true});
}
