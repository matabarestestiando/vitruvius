// A retry refers to an existing, unanswered owner message; it never reposts it.
export function pendingQuestion(messages){
 const last=messages.at(-1);
 if(!last||last.speaker!=='Propietario')return null;
 return {id:last.id,text:last.content,attachment_ids:(last.attachments||[]).map(a=>a.id)};
}
