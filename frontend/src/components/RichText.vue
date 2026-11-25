<script setup>
import {ref,watch,nextTick} from 'vue';
import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';
const props=defineProps({text:String});const root=ref(null);
const md=new MarkdownIt({html:false,linkify:true,breaks:true});
md.renderer.rules.image=()=>'<span>[Imagen externa omitida]</span>';
const html=ref('');let revision=0;
watch(()=>props.text,async text=>{const version=++revision;html.value=DOMPurify.sanitize(md.render(text||''));await nextTick();const nodes=root.value?.querySelectorAll('code.language-mermaid')||[];if(!nodes.length)return;const {default:mermaid}=await import('mermaid');mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'dark',htmlLabels:false,flowchart:{htmlLabels:false},maxTextSize:16000});for(const node of nodes){if(version!==revision)return;const code=node.textContent;if(code.includes(String.fromCharCode(92))||/https?:|data:|@import/i.test(code)||/%%\{|\bclick\s|javascript:|<\s*(script|iframe|foreignObject)/i.test(code))continue;try{const {svg}=await mermaid.render('diagram-'+crypto.randomUUID(),code);if(version!==revision)return;const figure=document.createElement('figure');figure.className='inline-diagram';figure.innerHTML=DOMPurify.sanitize(svg,{USE_PROFILES:{svg:true,svgFilters:true},FORBID_TAGS:['foreignObject','script','a','image']});node.parentElement.replaceWith(figure);}catch{/* Keep readable source when a diagram is invalid. */}}},{immediate:true});
</script>
<template><div ref="root" class="rich-text" v-html="html"/></template>
