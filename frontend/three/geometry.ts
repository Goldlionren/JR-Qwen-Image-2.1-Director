import * as T from 'three';
import { FAR, NEAR, RAD, rig, type DirectorState } from '../state';
export function directorCamera(s: DirectorState, camera = new T.PerspectiveCamera()) {
  const c=s.camera, az=c.azimuth*RAD, el=c.elevation*RAD;
  camera.position.set(-Math.sin(az)*Math.cos(el),Math.sin(el),Math.cos(az)*Math.cos(el)).multiplyScalar(c.distance).add(new T.Vector3(...c.target));
  camera.up.set(0,1,0); camera.lookAt(new T.Vector3(...c.target)); camera.rotateZ(c.roll*RAD);
  camera.fov=c.fov; camera.aspect=s.render.width/s.render.height; camera.near=NEAR; camera.far=FAR;
  camera.updateProjectionMatrix(); camera.updateMatrixWorld(true);
  return camera;
}
export function makeRig() {
  const root = new T.Group();
  const joints: Record<string,T.Object3D> = {};
  for (const def of rig.joints) {
    const joint=new T.Object3D(); joint.name=def.name; joint.position.fromArray(def.offset);
    (def.parent ? joints[def.parent] : root).add(joint); joints[def.name]=joint;
  }
  return {root,joints};
}
export type Rig = ReturnType<typeof makeRig>;
export function updateRig(r: Rig, s: DirectorState) {
  r.root.position.fromArray(s.actor.position);
  r.root.rotation.set(s.actor.pitch*RAD,-s.actor.yaw*RAD,s.actor.roll*RAD,'YXZ');
  r.root.scale.setScalar(s.actor.scale);
  for (const [name,j] of Object.entries(r.joints)) j.rotation.set(...s.pose.joints[name].map(v=>v*RAD) as [number,number,number], 'XYZ');
  r.root.updateMatrixWorld(true);
}
export function worldPoints(r: Rig) { return Object.fromEntries(Object.entries(r.joints).map(([n,j])=>[n,j.getWorldPosition(new T.Vector3())])); }
export function project(s: DirectorState, r: Rig) {
  const cam=directorCamera(s);
  return Object.fromEntries(Object.entries(worldPoints(r)).map(([n,p])=>{
    const depth=-p.clone().applyMatrix4(cam.matrixWorldInverse).z;
    const ndc=p.clone().project(cam);
    const xy=[(ndc.x+1)*s.render.width/2,(1-ndc.y)*s.render.height/2];
    return [n,{xy,depth,visible:depth>=NEAR && depth<=FAR && Math.abs(ndc.x)<=1 && Math.abs(ndc.y)<=1}];
  }));
}
