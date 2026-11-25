import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readEvents} from '../src/chatStream.js';
test('UTF-8 and SSE boundaries can split at every byte',async()=>{
 const bytes=new TextEncoder().encode('event: messages\ndata: [{"content":"á"}]\n\nevent: done\ndata: {}\n\n');const events=[];
 await readEvents(new Response(new ReadableStream({start(c){for(const b of bytes)c.enqueue(Uint8Array.of(b));c.close();}})),(event,data)=>events.push([event,data]));
 assert.equal(events[0][1][0].content,'á');assert.equal(events[1][0],'done');
});
test('truncated responses do not pretend the discussion finished',async()=>{
 await assert.rejects(readEvents(new Response('event: status\ndata: {}\n\n'),()=>{}),/interrumpió/);
});
test('authenticated HTTP errors are surfaced without rendering response HTML',async()=>{
 await assert.rejects(readEvents(new Response(JSON.stringify({detail:'Conversación ocupada'}),{status:409}),()=>{}),/Conversación ocupada/);
});
