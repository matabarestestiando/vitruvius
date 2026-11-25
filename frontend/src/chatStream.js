export async function readEvents(response,onEvent){
 if(!response.ok){let detail;try{detail=(await response.json()).detail;}catch{}throw Error(typeof detail==='string'?detail:'No se pudo iniciar la respuesta');}
 const reader=response.body.getReader(),decoder=new TextDecoder();let pending='',doneEvent=false;
 try{while(true){const {value,done}=await reader.read();pending+=decoder.decode(value,{stream:!done});let boundary;while((boundary=pending.indexOf('\n\n'))>=0){const block=pending.slice(0,boundary).replace(/\r/g,'');pending=pending.slice(boundary+2);const event=block.split('\n').find(l=>l.startsWith('event:'))?.slice(6).trim();const data=block.split('\n').filter(l=>l.startsWith('data:')).map(l=>l.slice(5).trimStart()).join('\n');if(data){const payload=JSON.parse(data);onEvent(event,payload);if(event==='done')doneEvent=true;}}if(done)break;}if(!doneEvent)throw Error('La conexión se interrumpió. El historial conserva las intervenciones terminadas.');}finally{reader.releaseLock();}
}
