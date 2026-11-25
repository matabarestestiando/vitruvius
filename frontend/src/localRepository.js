// Browser-only folder selection. File objects never acquire write access.
export const MAX_FILES=500, MAX_TEXT=2000000;
const denied=new Set(['node_modules','vendor','dist','build','coverage','__pycache__','venv','env','target','site-packages']);
const extensions=new Set(['py','ts','tsx','js','jsx','mjs','cjs','vue','svelte','md','txt','json','toml','yaml','yml','sql','go','rs','java','kt','kts','cs','c','h','cpp','hpp','rb','php','swift','html','css','scss','sh','r','ex','exs','scala','dart','xml','gradle','graphql','proto']);
export const secretPattern=/-----BEGIN (?:[A-Z ]*PRIVATE KEY)-----|\b(?:sk-or-v1-[A-Za-z0-9]{16,}|sk-[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})|(?:api[_-]?key|access[_-]?token|password|secret[_-]?key)\s*["']?\s*[:=]\s*["'][A-Za-z0-9_+/.=-]{12,}["']/i;
export function allowedCodePath(path){
 if(typeof path!=='string'||path.length>240||/[\\:\x00\n\r]/.test(path))return false;
 const parts=path.split('/');
 if(parts.some(p=>!p||p==='.'||p==='..'||p.startsWith('.')||denied.has(p.toLowerCase())||/credential|(?:^|[._-])secrets?(?:[._-]|$)|^id_(?:rsa|ed25519)/i.test(p)))return false;
 const name=parts.at(-1).toLowerCase();return extensions.has(name.split('.').at(-1))||['readme','dockerfile','makefile','cmakelists.txt','license'].includes(name);
}
export function selectFolder(fileList){
 const all=Array.from(fileList);const first=all.find(f=>f.webkitRelativePath?.includes('/'));
 if(!first)throw Error('Seleccione una carpeta, no archivos individuales.');
 const root=first.webkitRelativePath.split('/')[0];
 if(!root||root.length>120)throw Error('El nombre de la carpeta es demasiado largo.');
 const eligible=[];let excluded=0;
 for(const file of all){const relative=file.webkitRelativePath||'';if(!relative.startsWith(root+'/')){excluded++;continue;}const path=relative.slice(root.length+1);if(!allowedCodePath(path)||file.size>200000||!file.size){excluded++;continue;}eligible.push({path,file});}
 eligible.sort((a,b)=>(Number(!a.path.toLowerCase().startsWith('readme'))-Number(!b.path.toLowerCase().startsWith('readme')))||a.path.localeCompare(b.path));
 return {name:root,entries:eligible.slice(0,MAX_FILES),excluded,omitted:Math.max(0,eligible.length-MAX_FILES),total:all.length};
}
export async function prepareCopy(selection,selectedPaths){
 let characters=0,omitted=selection.omitted,blocked=0;const files=[];
 for(const {path,file} of selection.entries){if(!selectedPaths.includes(path)){omitted++;continue;}if(characters+file.size>MAX_TEXT){omitted++;continue;}
 const text=await file.text();
 if(text.includes('\u0000')||secretPattern.test(text)){blocked++;continue;}
 if(text.length>200000||characters+text.length>MAX_TEXT){omitted++;continue;}
 characters+=text.length;files.push({path,text});}
 if(!files.length)throw Error('No quedaron archivos compatibles para compartir. Revise la selección; los archivos con posibles claves se omiten.');
 return {name:selection.name,files,partial:Boolean(omitted||selection.excluded||blocked),consent:true,retention_hours:24,omitted,blocked,characters};
}
