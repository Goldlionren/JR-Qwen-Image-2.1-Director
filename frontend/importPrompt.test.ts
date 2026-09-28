import { describe,expect,it } from 'vitest';
import { buildCapturePrompt,type Prompt } from './importPrompt';

describe('Image import execution isolation',()=>{
  const graph:Prompt={
    '1':{class_type:'LoadImage',inputs:{image:'reference.png'}},
    '2':{class_type:'ImageScale',inputs:{image:['1',0],width:512}},
    '3':{class_type:'QwenImage21Director',inputs:{image:['2',0],director_state:'{}'}},
    '4':{class_type:'TextEncodeQwenImage21',inputs:{prompt:['3',0]}},
    '5':{class_type:'KSampler',inputs:{positive:['4',0]}},
  };
  it('queues only connected image ancestors and capture, with no downstream generation',()=>{
    const before=JSON.stringify(graph);
    const {prompt,captureId}=buildCapturePrompt(graph,'3','request');
    expect(Object.keys(prompt)).toEqual(['1','2',captureId]);
    expect(prompt[captureId].inputs.image).toEqual(['2',0]);
    expect(JSON.stringify(graph)).toBe(before);
    prompt['1'].inputs.image='changed.png';
    expect(graph['1'].inputs.image).toBe('reference.png');
  });
  it('rejects absent inputs and cycles before queueing',()=>{
    expect(()=>buildCapturePrompt(graph,'1','r')).toThrow('Director');
    expect(()=>buildCapturePrompt({'3':{class_type:'QwenImage21Director',inputs:{}}},'3','r')).toThrow('image');
    const cyclic:Prompt=structuredClone(graph);
    cyclic['1'].inputs.image=['2',0];
    expect(()=>buildCapturePrompt(cyclic,'3','r')).toThrow('循环');
  });
});
