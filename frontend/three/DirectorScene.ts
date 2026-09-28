import * as T from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { TransformControls } from 'three/examples/jsm/controls/TransformControls.js';
import { RAD, rig, wrap, type DirectorState } from '../state';
import { directorCamera, makeRig, updateRig, worldPoints } from './geometry';
import { drawPose } from './projection';
import { readRotation, solveIK } from './pose';

export class DirectorScene {
  readonly scene=new T.Scene();
  readonly actor=makeRig();
  private renderer:T.WebGLRenderer;
  private editor=new T.PerspectiveCamera(45,1,.05,200);
  private camera=new T.PerspectiveCamera();
  private guideCamera=new T.PerspectiveCamera();
  private orbit:OrbitControls;
  private gizmo:TransformControls;
  private helper:T.CameraHelper;
  private grid=new T.GridHelper(8,32,0x385664,0x1b303b);
  private axes=new T.AxesHelper(.6);
  private handles:T.Mesh[]=[];
  private bones:T.Line[]=[];
  private target=new T.Mesh(new T.SphereGeometry(.025,8,8),new T.MeshBasicMaterial({color:0xf9bd65}));
  private resize:ResizeObserver;
  private ray=new T.Raycaster();
  private drag:{x:number;y:number;type:string;plane?:T.Plane;name?:string}|null=null;
  private frame=0;
  private syncing=false;
  private disposed=false;
  private intersection:IntersectionObserver;
  private visible=true;
  constructor(private host:HTMLElement,private preview:HTMLCanvasElement,private state:DirectorState,private change:()=>void) {
    this.renderer=new T.WebGLRenderer({antialias:true,alpha:false});
    this.renderer.setPixelRatio(Math.min(devicePixelRatio,2)); this.renderer.setClearColor(0x0b151e);
    this.renderer.domElement.setAttribute('aria-label','3D Director stage'); this.renderer.domElement.style.touchAction='none';
    host.append(this.renderer.domElement);
    this.editor.position.set(2.5,2.0,3.3);
    this.orbit=new OrbitControls(this.editor,this.renderer.domElement); this.orbit.target.set(0,.95,0);
    this.orbit.mouseButtons={LEFT:null as unknown as T.MOUSE,MIDDLE:T.MOUSE.PAN,RIGHT:T.MOUSE.ROTATE};
    this.orbit.enableZoom=false;this.orbit.update(); this.orbit.addEventListener('change',this.schedule);
    this.scene.add(this.grid,this.axes,this.actor.root,this.target,new T.HemisphereLight(0xd5faff,0x314051,2));
    const light=new T.DirectionalLight(0xffffff,2);light.position.set(2,4,3);this.scene.add(light);
    this.helper=new T.CameraHelper(this.guideCamera);this.scene.add(this.helper);
    const geom=new T.SphereGeometry(.026,12,8);
    for(const def of rig.joints) {
      const index=rig.openpose_joints.indexOf(def.name),color=index<0?0x91b6ca:new T.Color(`rgb(${rig.colors[index].join(',')})`);
      const ball=new T.Mesh(geom,new T.MeshStandardMaterial({color,roughness:.45}));
      ball.userData.joint=def.name; this.actor.joints[def.name].add(ball);this.handles.push(ball);
      if(def.parent) {
        const line=new T.Line(new T.BufferGeometry().setFromPoints([new T.Vector3(),new T.Vector3()]),new T.LineBasicMaterial({color}));
        line.userData.child=def.name;line.userData.parent=def.parent;this.scene.add(line);this.bones.push(line);
      }
    }
    this.gizmo=new TransformControls(this.editor,this.renderer.domElement);this.gizmo.setMode('rotate');this.gizmo.setSpace('local');this.gizmo.setSize(.7);
    this.scene.add(this.gizmo.getHelper());
    this.gizmo.addEventListener('dragging-changed',e=>{this.orbit.enabled=!e.value;});
    this.gizmo.addEventListener('objectChange',()=>{
      if(this.syncing || !this.gizmo.object)return;
      this.state.pose.joints[this.gizmo.object.name]=readRotation(this.gizmo.object);
      this.state.pose.preset='Custom';this.change();this.update();
    });
    this.gizmo.addEventListener('change',this.schedule);
    const el=this.renderer.domElement;
    el.addEventListener('pointerdown',this.down);el.addEventListener('pointermove',this.move);el.addEventListener('pointerup',this.up);el.addEventListener('pointercancel',this.up);
    el.addEventListener('wheel',this.wheel,{passive:false});el.addEventListener('contextmenu',this.context);
    this.resize=new ResizeObserver(this.schedule);this.resize.observe(host);
    this.intersection=new IntersectionObserver(entries=>{this.visible=entries[0].isIntersecting;if(this.visible)this.schedule();});this.intersection.observe(host);
    this.update();
  }
  private context=(e:Event)=>e.preventDefault();
  private activeCamera() {return this.state.ui.view==='camera'?this.camera:this.editor;}
  setState(s:DirectorState) {this.state=s;this.update();}
  update() {
    if(this.disposed)return;
    this.syncing=true;
    updateRig(this.actor,this.state);directorCamera(this.state,this.camera);
    this.guideCamera.copy(this.camera);this.guideCamera.far=this.state.camera.distance+.6;this.guideCamera.updateProjectionMatrix();this.guideCamera.updateMatrixWorld(true);
    this.helper.update();this.target.position.fromArray(this.state.camera.target);
    const points=worldPoints(this.actor);
    for(const line of this.bones) { line.geometry.setFromPoints([points[line.userData.parent],points[line.userData.child]]); }
    for(const handle of this.handles) { const selected=handle.userData.joint===this.state.ui.selected_joint && this.state.ui.mode==='POSE';handle.scale.setScalar(selected?1.6:1); }
    this.gizmo.camera=this.activeCamera();
    if(this.state.ui.mode==='POSE' && !/(wrist|ankle)$/.test(this.state.ui.selected_joint)) this.gizmo.attach(this.actor.joints[this.state.ui.selected_joint]);
    else this.gizmo.detach();
    this.orbit.enabled=this.state.ui.view==='stage' && !this.gizmo.dragging;
    this.helper.visible=this.grid.visible=this.axes.visible=this.target.visible=this.state.ui.view==='stage';
    drawPose(this.preview,this.state,this.actor);
    this.syncing=false;this.schedule();
  }
  private setRay(e:PointerEvent) {
    const rect=this.renderer.domElement.getBoundingClientRect();
    // Main camera view is letterboxed to the exact output aspect ratio.
    let w=rect.width,h=rect.height,x=rect.left,y=rect.top;
    if(this.state.ui.view==='camera') {const ar=this.camera.aspect;if(w/h>ar){x+=(w-h*ar)/2;w=h*ar;}else{y+=(h-w/ar)/2;h=w/ar;}}
    this.ray.setFromCamera(new T.Vector2((e.clientX-x)/w*2-1,-(e.clientY-y)/h*2+1),this.activeCamera());
  }
  private down=(e:PointerEvent)=>{
    if(e.button!==0 || this.gizmo.axis || this.gizmo.dragging)return;
    const mode=this.state.ui.mode;
    this.setRay(e);
    if(mode==='POSE') {
      const hit=this.ray.intersectObjects(this.handles,false)[0];if(!hit)return;
      const name=String(hit.object.userData.joint);this.state.ui.selected_joint=name;
      this.change();this.update();
      if(!/(wrist|ankle)$/.test(name))return;
      const normal=this.activeCamera().getWorldDirection(new T.Vector3());
      this.drag={x:e.clientX,y:e.clientY,type:'ik',name,plane:new T.Plane().setFromNormalAndCoplanarPoint(normal,this.actor.joints[name].getWorldPosition(new T.Vector3()))};
    } else if(mode==='CAMERA') this.drag={x:e.clientX,y:e.clientY,type:e.shiftKey?'pan':'camera'};
    else this.drag={x:e.clientX,y:e.clientY,type:e.shiftKey?'actorMove':'actor'};
    this.renderer.domElement.setPointerCapture(e.pointerId);
  };
  private move=(e:PointerEvent)=>{
    if(!this.drag)return;
    const dx=e.clientX-this.drag.x,dy=e.clientY-this.drag.y;this.drag.x=e.clientX;this.drag.y=e.clientY;
    const c=this.state.camera,a=this.state.actor;
    if(this.drag.type==='camera') {c.azimuth=wrap(c.azimuth-dx*.4);c.elevation=T.MathUtils.clamp(c.elevation+dy*.3,-89,89);}
    if(this.drag.type==='pan') {
      const delta=new T.Vector3(-dx,dy,0).applyQuaternion(this.camera.quaternion).multiplyScalar(c.distance*.0015);
      c.target=c.target.map((v,i)=>T.MathUtils.clamp(v+delta.getComponent(i),-50,50)) as [number,number,number];
    }
    if(this.drag.type==='actor')a.yaw=wrap(a.yaw+dx*.5);
    if(this.drag.type==='actorMove') {a.position[0]=T.MathUtils.clamp(a.position[0]+dx*.003,-50,50);a.position[2]=T.MathUtils.clamp(a.position[2]+dy*.003,-50,50);}
    if(this.drag.type==='ik') {this.setRay(e);const p=this.ray.ray.intersectPlane(this.drag.plane!,new T.Vector3());if(p)solveIK(this.actor,this.state,this.drag.name!,p);}
    this.change();this.update();
  };
  private up=(e:PointerEvent)=>{this.drag=null;if(this.renderer.domElement.hasPointerCapture(e.pointerId))this.renderer.domElement.releasePointerCapture(e.pointerId);};
  private wheel=(e:WheelEvent)=>{
    e.preventDefault();e.stopPropagation();
    if(this.state.ui.mode==='CAMERA') {this.state.camera.distance=T.MathUtils.clamp(this.state.camera.distance*Math.exp(e.deltaY*.001),.2,50);this.change();this.update();}
    else if(this.state.ui.view==='stage') {this.editor.position.sub(this.orbit.target).multiplyScalar(Math.exp(e.deltaY*.001)).add(this.orbit.target);this.orbit.update();this.schedule();}
  };
  private schedule=()=>{if(!this.frame&&!this.disposed&&this.visible)this.frame=requestAnimationFrame(this.render);};
  private render=()=>{
    this.frame=0;if(this.disposed)return;
    const w=this.host.clientWidth,h=this.host.clientHeight;if(!w||!h)return;
    this.renderer.setSize(w,h,false);this.editor.aspect=w/h;this.editor.updateProjectionMatrix();
    this.renderer.setScissorTest(false);this.renderer.setViewport(0,0,w,h);this.renderer.clear();
    if(this.state.ui.view==='camera') {
      const ar=this.camera.aspect, vw=Math.min(w,h*ar),vh=vw/ar;
      this.renderer.setViewport((w-vw)/2,(h-vh)/2,vw,vh);this.renderer.setScissor((w-vw)/2,(h-vh)/2,vw,vh);this.renderer.setScissorTest(true);
    }
    this.renderer.render(this.scene,this.activeCamera());
  };
  dispose() {
    this.disposed=true;cancelAnimationFrame(this.frame);this.resize.disconnect();this.intersection.disconnect();
    this.orbit.dispose();this.gizmo.dispose();
    const el=this.renderer.domElement;
    el.removeEventListener('pointerdown',this.down);el.removeEventListener('pointermove',this.move);el.removeEventListener('pointerup',this.up);el.removeEventListener('pointercancel',this.up);el.removeEventListener('wheel',this.wheel);el.removeEventListener('contextmenu',this.context);
    const geometries=new Set<T.BufferGeometry>(),materials=new Set<T.Material>();
    this.scene.traverse(o=>{const mesh=o as T.Mesh;if(mesh.geometry)geometries.add(mesh.geometry);if(mesh.material)(Array.isArray(mesh.material)?mesh.material:[mesh.material]).forEach(m=>materials.add(m));});
    geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());this.renderer.dispose();el.remove();
  }
}
