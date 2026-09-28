import * as T from 'three';
import { FAR, NEAR, RAD, rig, type DirectorState } from '../state';
import { directorCamera, worldPoints, type Rig } from './geometry';

function clip(a:T.Vector3,b:T.Vector3,s:DirectorState): [T.Vector3,T.Vector3] | null {
  const t=Math.tan(s.camera.fov*RAD/2), ar=s.render.width/s.render.height;
  const planes=[[0,0,1,-NEAR],[0,0,-1,FAR],[1,0,t*ar,0],[-1,0,t*ar,0],[0,1,t,0],[0,-1,t,0]];
  let start=0,end=1;
  for(const [x,y,z,d] of planes) {
    const da=x*a.x+y*a.y+z*a.z+d,db=x*b.x+y*b.y+z*b.z+d;
    if(da<0 && db<0)return null;
    if(da<0 || db<0) { const f=da/(da-db); if(da<0)start=Math.max(start,f); else end=Math.min(end,f); }
  }
  return start>end ? null : [a.clone().lerp(b,start),a.clone().lerp(b,end)];
}
export function drawPose(canvas:HTMLCanvasElement,s:DirectorState,r:Rig) {
  // Same projected geometry and depth order as Python; raster antialiasing may differ.
  const max=512, scale=Math.min(1,max/Math.max(s.render.width,s.render.height));
  canvas.width=Math.round(s.render.width*scale); canvas.height=Math.round(s.render.height*scale);
  const ctx=canvas.getContext('2d')!,w=canvas.width,h=canvas.height;
  ctx.fillStyle='#000';ctx.fillRect(0,0,w,h);
  const cam=directorCamera(s), points=worldPoints(r);
  for(const p of Object.values(points)) { p.applyMatrix4(cam.matrixWorldInverse);p.z=-p.z; }
  const focal=h/(2*Math.tan(s.camera.fov*RAD/2));
  const xy=(p:T.Vector3)=>[w/2+focal*p.x/p.z,h/2-focal*p.y/p.z];
  const primitives: {depth:number;ps:number[][];color:number[];bone:boolean}[]=[];
  rig.edges.forEach(([a,b],i)=>{
    const segment=clip(points[rig.openpose_joints[a]],points[rig.openpose_joints[b]],s);
    if(segment) primitives.push({depth:(segment[0].z+segment[1].z)/2,ps:segment.map(xy),color:rig.colors[i],bone:true});
  });
  rig.openpose_joints.forEach((name,i)=>{
    const p=points[name],q=xy(p);
    if(p.z>=NEAR && p.z<=FAR && q[0]>=0 && q[0]<=w && q[1]>=0 && q[1]<=h) primitives.push({depth:p.z,ps:[q],color:rig.colors[i],bone:false});
  });
  const radius=Math.max(2,Math.min(s.render.width,s.render.height)/180)*scale;
  for(const p of primitives.sort((a,b)=>b.depth-a.depth)) {
    ctx.beginPath();
    if(p.bone) { ctx.strokeStyle=`rgb(${p.color.map(c=>Math.floor(c*.65)).join(',')})`;ctx.lineWidth=radius*1.25;ctx.moveTo(...p.ps[0] as [number,number]);ctx.lineTo(...p.ps[1] as [number,number]);ctx.stroke(); }
    else { ctx.fillStyle=`rgb(${p.color.join(',')})`;ctx.arc(p.ps[0][0],p.ps[0][1],radius,0,Math.PI*2);ctx.fill(); }
  }
}
