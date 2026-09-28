export type Prompt=Record<string,{class_type:string;inputs:Record<string,unknown>;[key:string]:unknown}>;

/** Isolate just the image source and its ancestors; never queue downstream Qwen. */
export function buildCapturePrompt(graph:Prompt,directorId:string,requestId:string) {
  if(graph[directorId]?.class_type!=='QwenImage21Director')throw Error('当前 Director 节点无法解析，请在主工作流中重试。');
  const link=graph[directorId]?.inputs.image;
  if(!Array.isArray(link)||link.length!==2||!graph[String(link[0])])throw Error('请先将 Load Image 或其他图像节点接到 Director 的 image 输入。');
  const prompt:Prompt={};
  const visiting=new Set<string>();
  function include(id:string) {
    if(visiting.has(id))throw Error('图像上游存在循环连接。');
    if(prompt[id])return;
    const node=graph[id];
    if(!node)throw Error(`找不到图像上游节点 ${id}`);
    visiting.add(id);
    for(const value of Object.values(node.inputs)) {
      if(Array.isArray(value)&&value.length===2&&typeof value[0]==='string'&&Number.isInteger(value[1]))include(value[0]);
    }
    prompt[id]=structuredClone(node);
    visiting.delete(id);
  }
  include(String(link[0]));
  const captureId=`jr_capture_${requestId}`;
  if(graph[captureId])throw Error('Import request ID collision');
  prompt[captureId]={class_type:'JRDirectorImageCapture',inputs:{image:link,request_id:requestId}};
  return {prompt,captureId};
}
