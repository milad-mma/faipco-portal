import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
const source = readFileSync(new URL('../src/utils/push.js', import.meta.url), 'utf8')
  .replace(/^import .*;\s*$/gm, '').replace(/^export /gm, '');
function fixture({permission = 'granted', oldKey = [1, 2, 3], fail = false, switchDuringSave = false} = {}) {
  let sid = 'session-A', current, creates = 0, removes = 0, prompts = 0;
  const saves = [], gates = [];
  const subscription = key => ({options: {applicationServerKey: new Uint8Array(key)},
    endpoint: 'https://example.invalid/push', toJSON() {return {endpoint: this.endpoint, keys: {auth:'a',p256dh:'b'}};},
    async unsubscribe() {removes++; current = null; return true;}});
  current = subscription(oldKey);
  const manager = {async getSubscription(){return current;}, async subscribe({applicationServerKey}) {creates++; current = subscription(applicationServerKey); return current;}};
  const context = {window:{PushManager: {}, Notification:{}, atob:s=>Buffer.from(s,'base64').toString('binary')},
    Notification:{permission, async requestPermission(){prompts++; return 'granted';}},
    localStorage:{getItem:()=>`x.${Buffer.from(JSON.stringify({sid})).toString('base64url')}.x`},
    navigator:{serviceWorker:{ready:Promise.resolve({pushManager:manager})}},
    fetchVapidPublicKey:async()=>Buffer.from([1,2,3]).toString('base64url'),
    subscribePush:async payload=>{saves.push(payload); if(switchDuringSave) sid='session-B'; if(fail) throw Error('offline');},
    setDevicePushEnabled:async (...args)=>gates.push(args), unsubscribePush:async()=>{},
    setTimeout,clearTimeout,Uint8Array,Date,Promise,Error,console};
  runInNewContext(source+'\nthis.api={enablePushNotifications,getPushRegistrationStatus};', context);
  return {...context.api, context, saves,gates, get creates(){return creates;},get removes(){return removes;},get prompts(){return prompts;}};
}
test('simultaneous registration is single flight and sends current SID', async()=>{
  const f=fixture(); await Promise.all([f.enablePushNotifications(),f.enablePushNotifications()]);
  assert.equal(f.saves.length,1);assert.equal(f.saves[0].session_marker,'session-A');assert.equal(f.gates.length,1);
  assert.equal(f.getPushRegistrationStatus().registered,true);
});
test('old VAPID subscription is replaced before registration', async()=>{
  const f=fixture({oldKey:[9]});await f.enablePushNotifications();assert.equal(f.removes,1);assert.equal(f.creates,1);assert.equal(f.saves.length,1);
});
test('permission alone is not a server registration; failure remains unregistered',async()=>{
  const f=fixture({fail:true});await assert.rejects(f.enablePushNotifications(),/offline/);assert.equal(f.getPushRegistrationStatus().registered,false);assert.equal(f.gates.length,0);
});
test('session switch during server save never enables stale local gate',async()=>{
  const f=fixture({switchDuringSave:true});await assert.rejects(f.enablePushNotifications());assert.equal(f.gates.length,0);assert.equal(f.getPushRegistrationStatus().registered,false);
});
test('background repair never prompts for permission',async()=>{
  const f=fixture({permission:'default'});await assert.rejects(f.enablePushNotifications({prompt:false}));assert.equal(f.prompts,0);assert.equal(f.saves.length,0);
});
test('permission revocation invalidates cached registration',async()=>{
  const f=fixture();await f.enablePushNotifications();f.context.Notification.permission='denied';assert.equal(f.getPushRegistrationStatus().registered,false);f.context.Notification.permission='granted';assert.equal(f.getPushRegistrationStatus().registered,false);
});
