const BASE='/wot/api';
function csrf(){return document.cookie.split('; ').find(x=>x.startsWith('wot_csrf='))?.split('=')[1]||''}
export async function api<T>(path:string,init:RequestInit={}):Promise<T>{const res=await fetch(BASE+path,{...init,credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf(),...init.headers}});if(!res.ok){const b=await res.json().catch(()=>({}));throw new Error(b.detail||`Błąd ${res.status}`)}return res.json()}
export const fmt=(d:string)=>new Intl.DateTimeFormat('pl-PL',{dateStyle:'medium',timeStyle:'short',timeZone:'Europe/Warsaw'}).format(new Date(d));
export function duration(s:number){if(s<=0)return 'zakończona';const d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60);return [d&&`${d}d`,h&&`${h}h`,`${m}min`].filter(Boolean).join(' ')}
