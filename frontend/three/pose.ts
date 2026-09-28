import * as T from 'three';
import { RAD, type DirectorState, type Vec3 } from '../state';
import { updateRig, type Rig } from './geometry';
function orient(r: Rig, s: DirectorState, name: string, child: string, target: T.Vector3) {
  const joint=r.joints[name], end=r.joints[child];
  const origin=joint.getWorldPosition(new T.Vector3());
  const current=end.getWorldPosition(new T.Vector3()).sub(origin).normalize();
  const desired=target.clone().sub(origin).normalize();
  if (desired.lengthSq()<1e-12) return;
  const q=joint.getWorldQuaternion(new T.Quaternion()).premultiply(new T.Quaternion().setFromUnitVectors(current,desired));
  q.premultiply(joint.parent!.getWorldQuaternion(new T.Quaternion()).invert());
  const e=new T.Euler().setFromQuaternion(q,'XYZ');
  s.pose.joints[name]=[e.x/RAD,e.y/RAD,e.z/RAD]; updateRig(r,s);
}
/** Analytic two-bone IK. Unreachable targets are clamped; immutable offsets preserve lengths. */
export function solveIK(r: Rig, s: DirectorState, endName: string, target: T.Vector3) {
  if (!/(wrist|ankle)$/.test(endName)) return;
  const end=r.joints[endName], mid=end.parent!, upper=mid.parent!;
  const a=upper.getWorldPosition(new T.Vector3()), b=mid.getWorldPosition(new T.Vector3()), c=end.getWorldPosition(new T.Vector3());
  const l1=a.distanceTo(b), l2=b.distanceTo(c), delta=target.clone().sub(a);
  const dist=T.MathUtils.clamp(delta.length(),Math.abs(l1-l2)+1e-5,l1+l2-1e-5);
  const axis=delta.lengthSq()>1e-10?delta.normalize():c.clone().sub(a).normalize();
  let pole=b.clone().sub(a).addScaledVector(axis,-b.clone().sub(a).dot(axis));
  if (pole.lengthSq()<1e-8) {
    pole=new T.Vector3(0,0,1).applyQuaternion(r.root.getWorldQuaternion(new T.Quaternion()));
    pole.addScaledVector(axis,-pole.dot(axis));
    if (pole.lengthSq()<1e-8) pole=new T.Vector3(1,0,0).cross(axis);
  }
  pole.normalize();
  const x=(l1*l1-l2*l2+dist*dist)/(2*dist), y=Math.sqrt(Math.max(0,l1*l1-x*x));
  const elbow=a.clone().addScaledVector(axis,x).addScaledVector(pole,y), goal=a.clone().addScaledVector(axis,dist);
  orient(r,s,upper.name,mid.name,elbow); orient(r,s,mid.name,end.name,goal);
  s.pose.preset='Custom';
}
export function readRotation(joint: T.Object3D): Vec3 { return [joint.rotation.x/RAD,joint.rotation.y/RAD,joint.rotation.z/RAD]; }
