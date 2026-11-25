import {test} from 'node:test';import assert from 'node:assert/strict';
import {pendingQuestion} from '../src/chatRecovery.js';
test('reload recovers an unanswered question by its existing ID and attachment IDs',()=>{
 const owner={id:'owner-id',speaker:'Propietario',content:'Original question',attachments:[{id:'private-file'}]};
 assert.deepEqual(pendingQuestion([owner]),{id:'owner-id',text:'Original question',attachment_ids:['private-file']});
 assert.equal(pendingQuestion([owner,{id:'reply',speaker:'Expert',content:'Answer'}]),null);
 assert.equal(pendingQuestion([]),null);
});
