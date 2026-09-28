// @ts-expect-error supplied by ComfyUI
import { api } from '/scripts/api.js';
import { buildCapturePrompt, type Prompt } from './importPrompt';
// @ts-expect-error supplied by ComfyUI
import { app } from '/scripts/app.js';
import type { DirectorState } from './state';

export type Detection = {token:string;people:{index:number;score:number;bbox:number[]}[];preview:string;width:number;height:number;batch_size:number};
export type PoseFit = {state:DirectorState;warnings:string[];fit_error_pixels:number;visible_keypoints:number};

async function request(path:string, body:unknown, signal:AbortSignal) {
  const response=await api.fetchApi(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal});
  const data=await response.json();
  if(!response.ok)throw Error(typeof data.error==='string'?data.error:data.error?.message||JSON.stringify(data.node_errors||data));
  return data;
}

export async function detectConnectedImage(node:any, progress:(s:string)=>void, signal:AbortSignal):Promise<Detection> {
  progress('正在取得 image 输入，只执行必要的上游节点…');
  const graph=await app.graphToPrompt();
  signal.throwIfAborted();
  // getRandomValues also works on a ComfyUI LAN URL served over plain HTTP.
  const requestId=Array.from(crypto.getRandomValues(new Uint32Array(4)),n=>n.toString(16).padStart(8,'0')).join('');
  const {prompt,captureId}=buildCapturePrompt(graph.output as Prompt,String(node.id),requestId);
  const queued=await request('/prompt',{prompt,client_id:api.clientId},signal);
  const deadline=Date.now()+10*60*1000;
  while(Date.now()<deadline) {
    signal.throwIfAborted();
    const response=await api.fetchApi(`/history/${encodeURIComponent(queued.prompt_id)}`,{signal});
    if(!response.ok)throw Error('无法读取图像任务状态，请重试。');
    const history=(await response.json())[queued.prompt_id];
    if(history) {
      const output=history.outputs?.[captureId];
      if(output?.request_id?.[0]===requestId && output?.jr_image_token?.[0]) {
        progress('正在本机识别人物…');
        return request('/jr-director/detect',{token:output.jr_image_token[0]},signal);
      }
      if(history.status?.status_str==='error'||history.status?.completed) {
        const detail=history.status?.messages?.find((m:any)=>m[0]==='execution_error')?.[1]?.exception_message;
        throw Error(detail||'上游图像任务未完成，请检查 ComfyUI 执行错误。');
      }
    }
    await new Promise<void>((resolve,reject)=>{
      const onAbort=()=>{clearTimeout(timer);reject(new DOMException('Cancelled','AbortError'));};
      const timer=setTimeout(()=>{signal.removeEventListener('abort',onAbort);resolve();},700);
      signal.addEventListener('abort',onAbort,{once:true});
    });
  }
  throw Error('取得上游图像超时。任务可能仍在队列中，请检查队列后重试。');
}

export async function fitDetectedPerson(token:string,index:number,state:string,signal:AbortSignal):Promise<PoseFit> {
  return request('/jr-director/fit',{token,person_index:index,state},signal);
}
